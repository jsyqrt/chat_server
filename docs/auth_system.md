# 用户管理与认证系统

## 1. 系统目标

用户管理与认证系统旨在提供安全可靠的用户身份验证，用户信息管理，以及授权访问控制功能。该模块是ZChat系统的基础，所有其他功能模块都依赖于它进行用户身份验证和权限控制。

### 主要目标

- 提供安全的用户注册和登录功能
- 管理用户身份和个人信息
- 实现基于JWT和Flask-Login的认证机制
- 提供权限管理和访问控制
- 支持手机号验证码登录方式
- 支持邀请码系统
- 管理用户会话和令牌生命周期

## 2. 系统设计

### 2.1 架构概述

用户认证系统采用JWT（JSON Web Token）和Flask-Login结合的认证机制。系统使用Redis存储临时验证信息如短信验证码，使用PostgreSQL存储用户的持久化数据。

### 2.2 数据模型

**用户表（User）**

```sql
CREATE TABLE USER (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL,
    avatar_name VARCHAR(255) NOT NULL DEFAULT '/static/images/default_avatar.png',
    nickname VARCHAR(100) NOT NULL,
    signature_text VARCHAR(255) NOT NULL DEFAULT '成为更好的自己',
    gender VARCHAR(20) NOT NULL DEFAULT '未知',
    edubg VARCHAR(50) NOT NULL DEFAULT '未知',
    yearofwork VARCHAR(20) NOT NULL DEFAULT '未知',
    interested_industries VARCHAR(500),
    interested_roles VARCHAR(500),
    interested_skills VARCHAR(500),
    account_type VARCHAR(20) NOT NULL DEFAULT 'free',
    daily_points INTEGER NOT NULL DEFAULT 80,
    points_reset_time REAL,
    subscription_start_time REAL,
    subscription_end_time REAL,
    invite_code VARCHAR(50),
    invited_by INTEGER,
    create_timestamp REAL DEFAULT EXTRACT(EPOCH FROM NOW())
);
```

**管理员用户表（AdminUser）**

```sql
CREATE TABLE ADMIN_USER (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES USER(id) NOT NULL
);
```

### 2.3 认证流程

1. **短信验证码登录流程**
   - 用户请求发送验证码到手机
   - 系统生成验证码并发送短信
   - 系统将验证码与手机号存储在Redis中（设置过期时间）
   - 用户提交手机号和验证码
   - 系统验证后，生成JWT令牌并返回给用户，同时使用Flask-Login进行会话管理

2. **JWT验证流程**
   - 用户请求包含JWT令牌
   - 系统验证JWT签名和有效期
   - 验证通过，系统从JWT中提取用户信息并授权访问

3. **Flask-Login验证流程**
   - 系统通过登录后设置的会话cookie验证用户身份
   - 用户在会话期间可以访问需要身份验证的资源
   - 注销时清除用户会话

### 2.4 安全考虑

- 验证码使用安全随机数生成，并混合时间戳和SECRET_KEY
- 验证码有效期由Redis的过期时间控制（通常为几分钟）
- 同一手机号在短时间内请求验证码会受到冷却时间限制
- 验证码使用后会从Redis中删除，防止重复使用
- 管理员权限通过专门的表格和装饰器控制

## 3. API接口

### 3.1 验证码发送

- **接口**：`/auth/verification_code`
- **方法**：GET（计划改为POST）
- **描述**：发送验证码到指定手机号
- **请求参数**：
  - `phone_number`：手机号
- **响应**：
  ```json
  {
    "code": "123456",
    "error": "succeed"
  }
  ```

### 3.2 验证码登录/注册

- **接口**：`/auth/login`
- **方法**：GET（计划改为POST）
- **描述**：使用验证码登录，不存在时自动注册
- **请求参数**：
  - `phone_number`：手机号
  - `verification_code`：验证码
  - `invite_code`：邀请码（可选）
- **响应**：
  ```json
  {
    "error": "login succeed",
    "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user_id": 1001,
    "invited_by": 1002
  }
  ```

### 3.3 登出

- **接口**：`/auth/logout`
- **方法**：GET（计划改为POST）
- **授权**：需要登录
- **描述**：登出当前用户
- **响应**：
  ```json
  {
    "error": "logout succeed",
    "user_id": 1001
  }
  ```

### 3.4 保护路由测试

- **接口**：`/auth/protected`
- **方法**：GET
- **授权**：需要登录
- **描述**：测试登录保护的路由
- **响应**：登录用户的ID

## 4. 代码实现细节

### 4.1 验证码管理

验证码存储在Redis中，并使用前缀和手机号作为键。系统同时存储验证码生成的时间戳，用于实现冷却期和过期时间检查。

```python
class RedisVerificationCode:
    def __init__(self, redis_client, expiration_time=60, cooldown_time=60):
        self.redis = redis_client
        self.expiration_time = expiration_time
        self.cooldown_time = cooldown_time
        self.prefix = "verification_code:"
        self.timestamp_prefix = "verification_timestamp:"
```

### 4.2 用户认证

系统同时使用Flask-Login和JWT进行认证。Flask-Login主要用于Web界面的会话管理，而JWT用于API的无状态认证。

```python
@login_manager.user_loader
def user_loader(user_id):
    user_ops = UserOps(session=db.session)
    u = user_ops.get_one(id=int(user_id))
    return LGUser(u)
```

### 4.3 邀请码系统

用户可以拥有邀请码，新用户注册时可以使用邀请码，系统会记录邀请关系并可能提供奖励。

```python
# 处理邀请者ID
inviter_id = None
if invite_code:
    try:
        user = User.query.filter_by(invite_code=invite_code).first()
        if user:
            inviter_id = user.id
    except Exception as e:
        current_app.logger.error(f"Error finding inviter for invite code {invite_code}: {str(e)}")
```

### 4.4 管理员权限

系统提供了`admin_required`装饰器，用于保护需要管理员权限的路由：

```python
def admin_required(func):
    @functools.wraps(func)
    def decorated_view(*args, **kwargs):
        user_id=current_user.get_id_int()
        admin_user_ops = AdminUserOps(session=db.session)
        is_admin = admin_user_ops.is_admin(user_id=user_id)
        if not is_admin:
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_view
```

## 5. 错误处理

| 状态码 | 错误信息 | 说明 |
|-------|---------|-----|
| 400 | Invalid Phone Number or Verification Code! | 请求参数无效 |
| 400 | Verification code not found or expired | 验证码不存在或已过期 |
| 400 | Verification code has expired | 验证码已过期 |
| 400 | Incorrect verification code | 验证码错误 |
| 400 | No such user! | 用户不存在 |
| 401 | Unauthorized | 未授权访问 |
| 429 | Please wait before requesting another code | 请求过于频繁 |

## 6. 集成点

- **与邀请模块集成**：注册时支持邀请码，记录用户关系
- **与订阅模块集成**：用户表中包含账户类型和订阅信息
- **与消息模块集成**：用户有与聊天会话的关联关系
- **与积分系统集成**：用户账户类型决定每日积分额度

## 7. 未来计划

- 将GET请求方法改为更安全的POST方法
- 可能需要提供JWT刷新机制
- 完善第三方登录集成
- 增强安全检查和防护措施