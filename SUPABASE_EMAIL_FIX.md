# 📧 Supabase Email Configuration

## ⚠️ Issue: High Email Bounce Rate

Supabase detected high bounce rates from your project because we've been testing with fake email addresses like `test@tradiqai.com`.

## 🔧 Solution: Disable Email Confirmation (Development)

For development, disable email confirmation so you can test without real emails:

### Steps:

1. **Open Supabase Authentication Settings:**
   👉 https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo/auth/providers

2. **Scroll to "Email Auth" section**

3. **Toggle OFF: "Confirm email"**
   - This allows users to sign up without email verification
   - Perfect for development and testing

4. **Save changes**

Now you can test registration without needing real email addresses!

## ✅ Alternative: Use Real Email Addresses

If you want to keep email confirmation ON:

```python
# Use your real email for testing
test_user = UserRegister(
    email="your.real.email@gmail.com",  # Real email
    password="test123456",
    username="testuser"
)
```

## 🚀 Production Setup: Custom SMTP

For production, use your own email provider:

### Recommended Providers:
- **SendGrid** (12k free emails/month)
- **Mailgun** (5k free emails/month)  
- **AWS SES** (62k free emails/month on AWS)
- **Resend** (3k free emails/month)

### Configure in Supabase:

1. Go to: https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo/auth/providers
2. Scroll to "SMTP Settings"
3. Add your provider credentials:
   - SMTP Host
   - SMTP Port (usually 587)
   - Username
   - Password
   - Sender Email
   - Sender Name

## 📝 Current Status:

- ❌ Email confirmation: **ENABLED** (causing bounces)
- ✅ Solution: **Disable for development** OR use real emails
- 🎯 For production: **Setup custom SMTP provider**

## 🔗 Quick Links:

- **Auth Settings**: https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo/auth/providers
- **SMTP Settings**: https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo/settings/auth#smtp-settings
- **Email Templates**: https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo/auth/templates

---

**Recommended Action:** Disable email confirmation for development testing.
