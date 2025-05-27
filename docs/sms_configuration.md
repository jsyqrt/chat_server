# 阿里云短信服务配置说明

## 环境变量配置

为了使用阿里云短信验证码功能，需要配置以下环境变量：

### 必需的环境变量

```bash
# 阿里云AccessKey ID
export ALIBABA_CLOUD_ACCESS_KEY_ID="your_access_key_id"

# 阿里云AccessKey Secret
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your_access_key_secret"
```

### 可选的环境变量

```bash
# 短信签名（默认值：原猫信息）
export ALI_SMS_SIGN_NAME="your_sms_signature"

# 短信模板代码（默认值：SMS_319000120）
export ALI_SMS_TEMPLATE_CODE="your_template_code"
```

## 短信模板要求

短信模板必须包含一个名为 `code` 的变量，用于传递验证码。

示例模板内容：
```
您的验证码是：${code}，请在5分钟内完成验证。
```

## 功能特性

1. **真实短信发送**：集成阿里云短信服务，发送真实的验证码短信
2. **开发环境兼容**：在开发环境下，如果短信发送失败，仍会返回验证码用于测试
3. **生产环境安全**：在生产环境下，短信发送失败时不会返回验证码
4. **详细日志记录**：包含完整的日志记录，便于调试和监控
5. **异常处理**：完善的异常处理机制，包含详细的错误信息
6. **API监控集成**：集成Prometheus监控，跟踪SMS服务的成功率和性能指标

## 使用的API端点

- `/auth/verification_code` - 发送验证码短信
- `/auth/login` - 手机号验证码登录
- `/auth/bind_phone` - 绑定手机号

## 日志级别

- `INFO`: 正常操作日志（发送成功、验证成功等）
- `WARNING`: 警告日志（发送失败、验证码错误等）
- `ERROR`: 错误日志（异常情况、系统错误等）

## 监控指标

SMS服务集成了Prometheus监控，提供以下指标：

### API调用指标
- `api_requests_total{api_name="sms_send_verification", status="success"}` - SMS发送成功次数
- `api_requests_total{api_name="sms_send_verification", status="failed"}` - SMS发送失败次数

### 监控端点
访问 `/metrics` 端点可以获取所有监控指标，包括SMS服务的调用统计。

### 监控状态分类
- **success**: SMS发送成功（阿里云返回OK状态）
- **failed**: SMS发送失败（包括阿里云返回错误状态、响应为空、网络异常等所有失败情况）

### 监控特点
- 统一指标名称：不区分同步/异步调用，统一使用 `sms_send_verification`
- 最细粒度记录：每次SMS发送尝试都会被记录
- 简化状态：只区分成功和失败两种状态，便于监控和告警

## 安全注意事项

1. 请妥善保管阿里云AccessKey，不要在代码中硬编码
2. 建议使用阿里云RAM子账号，并只授予短信服务相关权限
3. 在生产环境中确保环境变量的安全性
4. 定期轮换AccessKey以提高安全性
5. 通过监控指标及时发现SMS服务异常，确保服务可用性