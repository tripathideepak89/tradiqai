# Configure Supabase Site URL

## Issue
Email verification links are redirecting to `localhost:3000` instead of `localhost:9000`.

## Solution

### 1. **Update Site URL in Supabase**

👉 **Go to**: https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo/auth/url-configuration

**Set these values:**

- **Site URL**: `http://localhost:9000`
- **Redirect URLs**: 
  ```
  http://localhost:9000
  http://localhost:9000/**
  ```

### 2. **Save Changes**

Click "Save" at the bottom of the page.

### 3. **Test Again**

Register a new user - the verification email will now redirect to the correct dashboard URL.

---

## Alternative: Disable Email Confirmation (Development)

If you don't want to deal with email verification during development:

👉 **Go to**: https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo/auth/providers

1. Scroll to **"Email Auth"** section
2. Toggle **OFF**: "Confirm email"
3. **Save**

Now users can register without email verification!

---

## For Production

When deploying to production, update the Site URL to your actual domain:

- **Site URL**: `https://yourdomain.com`
- **Redirect URLs**: `https://yourdomain.com/**`
