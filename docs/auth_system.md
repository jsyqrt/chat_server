# 用户管理与认证系统

## 1. 系统目标

用户管理与认证系统旨在提供安全可靠的用户身份验证，用户信息管理，以及授权访问控制功能。该模块是ZChat系统的基础，所有其他功能模块都依赖于它进行用户身份验证和权限控制。

### 主要目标

- 提供安全的用户注册和登录功能
- 管理用户身份和个人信息
- 实现基于JWT和Flask-Login的认证机制
- 提供权限管理和访问控制
- 支持手机号验证码登录方式
- 支持邮箱密码注册和登录方式
- 支持邮箱验证功能
- 支持密码找回功能
- 支持Google和GitHub OAuth登录方式
- 支持JWT令牌刷新机制
- 提供用户资料管理接口
- 支持邀请码系统
- 管理用户会话和令牌生命周期

## 2. 系统设计

### 2.1 架构概述

用户认证系统采用JWT（JSON Web Token）和Flask-Login结合的认证机制。系统使用Redis存储临时验证信息如短信验证码、邮箱验证令牌和JWT刷新令牌，使用PostgreSQL存储用户的持久化数据，使用Flask-Mail实现邮件发送服务。系统支持多种身份验证方式，包括手机验证码、邮箱密码和第三方OAuth认证。

### 2.2 数据模型

**用户表（User）**

```sql
CREATE TABLE USER (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20),
    email VARCHAR(120) UNIQUE,
    email_verified BOOLEAN DEFAULT FALSE,
    password_hash VARCHAR(256),
    reset_token VARCHAR(100),
    reset_token_expiry REAL,
    oauth_provider VARCHAR(50),
    oauth_id VARCHAR(100),
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
   - 系统验证后，生成JWT访问令牌和刷新令牌，并返回给用户，同时使用Flask-Login进行会话管理

2. **邮箱密码注册流程**
   - 用户提交邮箱和密码
   - 系统生成验证令牌并发送邮件
   - 用户点击邮件中的验证链接
   - 系统验证令牌并激活用户账号

3. **邮箱密码登录流程**
   - 用户提交邮箱和密码
   - 系统验证密码并检查邮箱是否已验证
   - 验证通过后，生成JWT访问令牌和刷新令牌，并返回给用户

4. **密码找回流程**
   - 用户提交邮箱
   - 系统生成密码重置令牌并发送邮件
   - 用户点击邮件中的重置链接并输入新密码
   - 系统验证令牌并更新用户密码

5. **OAuth登录流程（Google/GitHub）**
   - 用户点击OAuth登录按钮
   - 重定向到OAuth提供商授权页面
   - 用户授权后返回应用
   - 系统获取并验证用户信息
   - 查找或创建用户并登录
   - 生成JWT访问令牌和刷新令牌，并返回给用户

6. **JWT刷新流程**
   - 用户访问令牌过期时，使用刷新令牌请求新的访问令牌
   - 系统验证刷新令牌并生成新的访问令牌
   - 返回新的访问令牌给用户

7. **JWT验证流程**
   - 用户请求包含JWT令牌
   - 系统验证JWT签名和有效期
   - 验证通过，系统从JWT中提取用户信息并授权访问

8. **Flask-Login验证流程**
   - 系统通过登录后设置的会话cookie验证用户身份
   - 用户在会话期间可以访问需要身份验证的资源
   - 注销时清除用户会话

### 2.4 安全考虑

- 所有API接口使用POST方法，确保敏感数据不会通过URL参数暴露
- 验证码使用安全随机数生成，并混合时间戳和SECRET_KEY
- 验证码有效期由Redis的过期时间控制（通常为几分钟）
- 密码使用bcrypt进行安全哈希存储
- 重置密码和邮箱验证令牌使用UUID生成，时效性由Redis控制
- 邮箱验证确保用户邮箱的真实性
- OAuth登录通过可信第三方验证用户身份
- JWT访问令牌短期有效，刷新令牌长期有效
- 同一手机号在短时间内请求验证码会受到冷却时间限制
- 验证码和令牌使用后会从Redis中删除，防止重复使用
- 管理员权限通过专门的表格和装饰器控制

## 3. API接口

### 3.1 手机验证码相关

#### 3.1.1 验证码发送

- **接口**：`/auth/verification_code`
- **方法**：POST
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

#### 3.1.2 验证码登录/注册

- **接口**：`/auth/login`
- **方法**：POST
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
    "refresh_token": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": 1001,
    "invited_by": 1002
  }
  ```

### 3.2 邮箱注册和登录

#### 3.2.1 邮箱注册

- **接口**：`/auth/register`
- **方法**：POST
- **描述**：使用邮箱和密码注册新用户
- **请求参数**：
  - `email`：邮箱
  - `password`：密码
  - `invite_code`：邀请码（可选）
- **响应**：
  ```json
  {
    "error": "register succeed",
    "message": "注册成功，请查收验证邮件",
    "user_id": 1001
  }
  ```

#### 3.2.2 邮箱验证

- **接口**：`/auth/verify_email`
- **方法**：GET, POST
- **描述**：验证用户邮箱
- **GET请求参数**：
  - `user_id`：用户ID
  - `token`：验证令牌
- **POST请求参数**：
  - `user_id`：用户ID
  - `token`：验证令牌
- **响应**：
  ```json
  {
    "error": "verify succeed",
    "message": "邮箱验证成功，现在可以登录了"
  }
  ```

#### 3.2.3 邮箱密码登录

- **接口**：`/auth/email_login`
- **方法**：POST
- **描述**：使用邮箱和密码登录
- **请求参数**：
  - `email`：邮箱
  - `password`：密码
- **响应**：
  ```json
  {
    "error": "login succeed",
    "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": 1001
  }
  ```

### 3.3 密码找回

#### 3.3.1 请求找回密码

- **接口**：`/auth/forgot_password`
- **方法**：POST
- **描述**：申请找回密码，发送重置邮件
- **请求参数**：
  - `email`：邮箱
- **响应**：
  ```json
  {
    "message": "重置密码的邮件已发送，请查收"
  }
  ```

#### 3.3.2 重置密码

- **接口**：`/auth/reset_password`
- **方法**：GET, POST
- **描述**：通过令牌重置密码
- **GET请求参数**：
  - `token`：重置令牌
- **POST请求参数**：
  - `token`：重置令牌
  - `new_password`：新密码
- **响应**：
  ```json
  {
    "message": "密码重置成功，请使用新密码登录"
  }
  ```

### 3.4 OAuth登录

#### 3.4.1 发起Google登录

- **接口**：`/auth/google_login`
- **方法**：GET
- **描述**：重定向到Google登录页面
- **响应**：重定向到Google授权页面

#### 3.4.2 Google回调

- **接口**：`/auth/google_callback`
- **方法**：GET
- **描述**：处理Google登录回调
- **响应**：
  ```json
  {
    "error": "login succeed",
    "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": 1001
  }
  ```

#### 3.4.3 发起GitHub登录

- **接口**：`/auth/github_login`
- **方法**：GET
- **描述**：重定向到GitHub登录页面
- **响应**：重定向到GitHub授权页面

#### 3.4.4 GitHub回调

- **接口**：`/auth/github_callback`
- **方法**：GET
- **描述**：处理GitHub登录回调
- **响应**：
  ```json
  {
    "error": "login succeed",
    "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": 1001
  }
  ```

### 3.5 JWT令牌刷新

- **接口**：`/auth/refresh_token`
- **方法**：POST
- **描述**：使用刷新令牌获取新的访问令牌
- **请求参数**：
  - `refresh_token`：刷新令牌
- **响应**：
  ```json
  {
    "error": "refresh succeed",
    "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user_id": 1001
  }
  ```

### 3.6 账号管理

#### 3.6.1 修改密码

- **接口**：`/auth/change_password`
- **方法**：POST
- **授权**：需要登录
- **描述**：修改账号密码
- **请求参数**：
  - `current_password`：当前密码
  - `new_password`：新密码
- **响应**：
  ```json
  {
    "message": "密码修改成功"
  }
  ```

#### 3.6.2 绑定手机号

- **接口**：`/auth/bind_phone`
- **方法**：POST
- **授权**：需要登录
- **描述**：绑定手机号
- **请求参数**：
  - `phone_number`：手机号
  - `verification_code`：验证码
- **响应**：
  ```json
  {
    "message": "手机号绑定成功"
  }
  ```

#### 3.6.3 解绑手机号

- **接口**：`/auth/unbind_phone`
- **方法**：POST
- **授权**：需要登录
- **描述**：解绑手机号
- **响应**：
  ```json
  {
    "message": "手机号解绑成功"
  }
  ```

#### 3.6.4 绑定邮箱

- **接口**：`/auth/bind_email`
- **方法**：POST
- **授权**：需要登录
- **描述**：绑定邮箱
- **请求参数**：
  - `email`：邮箱
- **响应**：
  ```json
  {
    "message": "邮箱绑定成功，请查收验证邮件"
  }
  ```

#### 3.6.5 解绑邮箱

- **接口**：`/auth/unbind_email`
- **方法**：POST
- **授权**：需要登录
- **描述**：解绑邮箱
- **响应**：
  ```json
  {
    "message": "邮箱解绑成功"
  }
  ```

### 3.7 其他接口

#### 3.7.1 登出

- **接口**：`/auth/logout`
- **方法**：POST
- **授权**：需要登录
- **描述**：登出当前用户
- **请求参数**：
  - `refresh_token`：刷新令牌（可选）
- **响应**：
  ```json
  {
    "error": "logout succeed",
    "user_id": 1001
  }
  ```

#### 3.7.2 保护路由测试

- **接口**：`/auth/protected`
- **方法**：GET
- **授权**：需要登录
- **描述**：测试登录保护的路由
- **响应**：登录用户的ID

## 4. 代码实现细节

### 4.1 认证模块

系统同时支持手机号验证码、邮箱密码和OAuth两种认证方式，并支持JWT令牌刷新。认证信息通过JWT令牌和Flask-Login会话进行管理。

```python
# 初始化OAuth客户端
oauth = OAuth()
def init_app(app):
    login_manager.init_app(app)
    oauth.init_app(app)

    # 配置Google OAuth
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        # ... 其他配置 ...
    )

    # 配置GitHub OAuth
    oauth.register(
        name='github',
        client_id=app.config.get('GITHUB_CLIENT_ID'),
        # ... 其他配置 ...
    )
```

### 4.2 用户模型扩展

用户模型支持多种登录方式，包括手机号、邮箱和OAuth：

```python
class User(UserMixin, db.Model):
    # ... 其他字段 ...
    phone_number = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True, unique=True)
    email_verified = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(256), nullable=True)
    oauth_provider = db.Column(db.String(50), nullable=True)
    oauth_id = db.Column(db.String(100), nullable=True)

    # 密码相关方法
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
```

### 4.3 JWT令牌管理

系统使用访问令牌和刷新令牌两种令牌，访问令牌短期有效，刷新令牌长期有效：

```python
def generate_jwt_token(user_id, expiration=3600):
    """生成JWT访问令牌"""
    payload = {
        'user_id': user_id,
        'exp': time.time() + expiration,
        'iat': time.time()
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'])

def generate_refresh_token(user_id):
    """生成刷新令牌并存储到Redis"""
    token = str(uuid.uuid4())
    token_store = RedisTokenStore(current_app.redis)
    token_store.store_refresh_token(user_id, token)
    return token
```

### 4.4 令牌管理

系统使用Redis存储和管理验证码、邮箱验证令牌、密码重置令牌和JWT刷新令牌：

```python
class RedisTokenStore:
    """Redis存储验证令牌"""
    def __init__(self, redis_client, expiration_time=3600):
        self.redis = redis_client
        self.expiration_time = expiration_time
        self.verification_prefix = "email_verification:"
        self.reset_prefix = "password_reset:"
        self.refresh_prefix = "jwt_refresh:"

    # ... 验证和重置令牌方法 ...

    def store_refresh_token(self, user_id, token, expiration_time=604800):
        """存储JWT刷新令牌，默认7天过期"""
        key = f"{self.refresh_prefix}{token}"
        self.redis.set(key, str(user_id), ex=expiration_time)

    def verify_refresh_token(self, token):
        """验证刷新令牌，返回用户ID"""
        key = f"{self.refresh_prefix}{token}"
        user_id = self.redis.get(key)
        if user_id:
            return int(user_id)
        return None
```

### 4.5 邮件服务

系统使用Flask-Mail异步发送邮件，确保不会阻塞主应用流程：

```python
def send_async_email(app, msg):
    """异步发送邮件的后台任务"""
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f"Send email failed: {str(e)}")

def send_email(subject, recipients, html_body, text_body=None):
    # ... 代码实现 ...
    # 创建后台线程发送邮件
    thr = Thread(target=send_async_email, args=[app, msg])
    thr.start()
```

## 5. 错误处理

| 状态码 | 错误信息 | 说明 |
|-------|---------|-----|
| 400 | Invalid Phone Number or Verification Code! | 请求参数无效 |
| 400 | Verification code not found or expired | 验证码不存在或已过期 |
| 400 | Verification code has expired | 验证码已过期 |
| 400 | Incorrect verification code | 验证码错误 |
| 400 | 请提供邮箱和密码 | 注册或登录缺少必要参数 |
| 400 | 邮箱格式不正确 | 邮箱格式无效 |
| 400 | 密码长度至少为8位 | 密码强度不足 |
| 400 | 该邮箱已注册 | 邮箱已被使用 |
| 400 | 无效的请求参数 | 请求参数缺失或无效 |
| 400 | 该手机号已被其他账号绑定 | 手机号已被使用 |
| 400 | 当前账号未绑定手机号 | 请求解绑不存在的手机号 |
| 400 | 无法解绑手机号，账号必须保留至少一种登录方式 | 安全限制 |
| 400 | 当前账号未绑定邮箱 | 请求解绑不存在的邮箱 |
| 400 | 无法解绑邮箱，账号必须保留至少一种登录方式 | 安全限制 |
| 400 | 缺少刷新令牌 | 刷新令牌缺失 |
| 401 | Unauthorized | 未授权访问 |
| 401 | 邮箱或密码错误 | 登录凭据错误 |
| 401 | 当前密码错误 | 修改密码验证失败 |
| 401 | 无效的刷新令牌或已过期 | 刷新令牌验证失败 |
| 403 | 邮箱未验证 | 需要先验证邮箱 |
| 429 | Please wait before requesting another code | 请求过于频繁 |
| 500 | 注册失败 | 服务器内部错误 |
| 500 | 发送验证邮件失败 | 邮件服务错误 |
| 500 | 手机号绑定失败 | 数据库更新失败 |
| 500 | 手机号解绑失败 | 数据库更新失败 |
| 500 | 邮箱绑定失败 | 数据库更新失败 |
| 500 | 邮箱解绑失败 | 数据库更新失败 |

## 6. 集成点

- **与邀请模块集成**：注册时支持邀请码，记录用户关系
- **与订阅模块集成**：用户表中包含账户类型和订阅信息
- **与消息模块集成**：用户有与聊天会话的关联关系
- **与积分系统集成**：用户账户类型决定每日积分额度
- **与邮件服务集成**：用于发送验证和重置密码邮件
- **与第三方OAuth集成**：支持Google和GitHub账号登录
- **与用户资料管理集成**：提供修改密码、绑定或解绑手机号/邮箱等接口

## 7. 实施进度

- [x] 更新User数据模型
- [x] 添加邮件服务功能
- [x] 实现邮箱和密码注册API
- [x] 实现邮箱验证API
- [x] 实现邮箱密码登录API
- [x] 实现密码找回请求API
- [x] 实现密码重置API
- [x] 实现Google OAuth登录API
- [x] 将GET请求改为POST请求
- [x] 实现GitHub OAuth登录API
- [x] 实现JWT令牌刷新机制
- [x] 实现用户资料管理接口
- [x] 更新文档

## 8. 未来计划

- 实现更多第三方登录方式，如微信、Apple等
- 添加两步验证功能
- 实现记住登录状态功能
- 优化令牌管理，支持令牌撤销
- 实现用户登录历史和设备管理
- 添加安全日志和异常登录检测
- 完善用户权限系统