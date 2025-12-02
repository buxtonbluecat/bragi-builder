# Azure AD Authentication Setup Guide

This guide will help you set up Azure AD (Microsoft Entra ID) authentication for Bragi Builder.

## Prerequisites

- An Azure subscription
- Azure AD (Microsoft Entra ID) tenant access
- Admin access to register applications in Azure AD

## Step 1: Register an Application in Azure AD

1. **Navigate to Azure Portal**
   - Go to [Azure Portal](https://portal.azure.com)
   - Sign in with an account that has permissions to register applications

2. **Open Azure Active Directory**
   - Search for "Microsoft Entra ID" or "Azure Active Directory" in the search bar
   - Click on "App registrations" in the left menu

3. **Register a New Application**
   - Click "+ New registration"
   - **Name**: Enter a name (e.g., "Bragi Builder")
   - **Supported account types**: Choose based on your needs:
     - "Accounts in this organizational directory only" (Single tenant)
     - "Accounts in any organizational directory" (Multi-tenant)
   - **Redirect URI**: 
     - Platform: Web
     - URI: `https://bragi-builder.uksouth.cloudapp.azure.com/login/authorized`
     - (Or your custom domain: `https://your-domain.com/login/authorized`)
   - Click "Register"

4. **Note Down Application Details**
   - **Application (client) ID**: Copy this value (you'll need it)
   - **Directory (tenant) ID**: Copy this value (you'll need it)

## Step 2: Create a Client Secret

1. **Navigate to Certificates & secrets**
   - In your app registration, click "Certificates & secrets" in the left menu
   - Click "+ New client secret"
   - **Description**: Enter a description (e.g., "Bragi Builder Secret")
   - **Expires**: Choose expiration (recommend 12-24 months)
   - Click "Add"

2. **Copy the Secret Value**
   - ⚠️ **IMPORTANT**: Copy the secret value immediately - it won't be shown again!
   - Store it securely (you'll need it for environment variables)

## Step 3: Configure API Permissions

1. **Navigate to API permissions**
   - Click "API permissions" in the left menu
   - Click "+ Add a permission"
   - Select "Microsoft Graph"
   - Select "Delegated permissions"
   - Add the following permissions:
     - `User.Read` (to read user profile)
   - Click "Add permissions"

2. **Grant Admin Consent** (if required)
   - If you see "Grant admin consent for [Your Organization]", click it
   - This allows all users in your organization to use the app

## Step 4: Configure Redirect URIs

1. **Navigate to Authentication**
   - Click "Authentication" in the left menu
   - Under "Redirect URIs", ensure you have:
     - `https://bragi-builder.uksouth.cloudapp.azure.com/login/authorized`
     - `http://localhost:8080/login/authorized` (for local development)
   - If using a custom domain, add:
     - `https://your-domain.com/login/authorized`

2. **Configure Implicit Grant** (if needed)
   - Under "Implicit grant and hybrid flows", you typically don't need to enable anything
   - The authorization code flow is used by default

## Step 5: Set Environment Variables on VM

SSH into your VM and set the following environment variables:

```bash
# SSH into VM
ssh -i ~/.ssh/id_rsa_bragi azureuser@bragi-builder.uksouth.cloudapp.azure.com

# Edit the systemd service file
sudo nano /etc/systemd/system/bragi-builder.service
```

Add these environment variables to the `[Service]` section:

```ini
Environment="AZURE_AD_TENANT_ID=your-tenant-id-here"
Environment="AZURE_AD_CLIENT_ID=your-client-id-here"
Environment="AZURE_AD_CLIENT_SECRET=your-client-secret-here"
Environment="AZURE_AD_REDIRECT_URI=https://bragi-builder.uksouth.cloudapp.azure.com/login/authorized"
```

**Example:**
```ini
[Service]
Type=simple
User=bragi
WorkingDirectory=/opt/bragi-builder
Environment="PATH=/opt/bragi-builder/venv/bin"
Environment="FLASK_ENV=production"
Environment="PORT=8080"
Environment="AZURE_SUBSCRIPTION_ID=693bb5f4-bea9-4714-b990-55d5a4032ae1"
Environment="AZURE_AD_TENANT_ID=ccebb17e-cbf7-4aa3-b2ab-8e65565864a0"
Environment="AZURE_AD_CLIENT_ID=your-app-client-id"
Environment="AZURE_AD_CLIENT_SECRET=your-client-secret-value"
Environment="AZURE_AD_REDIRECT_URI=https://bragi-builder.uksouth.cloudapp.azure.com/login/authorized"
ExecStart=/opt/bragi-builder/venv/bin/gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 600 --worker-class gevent --worker-connections 1000 --log-level info --access-logfile - --error-logfile - app:app
Restart=always
RestartSec=10
```

After editing, reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart bragi-builder
sudo systemctl status bragi-builder
```

## Step 6: Verify Authentication

1. **Access the Application**
   - Navigate to: `https://bragi-builder.uksouth.cloudapp.azure.com`
   - You should be redirected to the login page

2. **Test Login**
   - Click "Sign in with Microsoft"
   - Sign in with your Azure AD account
   - You should be redirected back to the application

3. **Check Session**
   - After login, you should see your name in the sidebar
   - All routes should now be accessible

## Troubleshooting

### Issue: "Authentication error" or redirect fails

**Check:**
1. Redirect URI matches exactly in Azure AD app registration
2. Client secret hasn't expired
3. Environment variables are set correctly
4. Check application logs: `sudo journalctl -u bragi-builder -f`

### Issue: "Failed to acquire access token"

**Check:**
1. Client ID and Client Secret are correct
2. Tenant ID is correct
3. API permissions are granted
4. Admin consent has been granted (if required)

### Issue: Users can't sign in

**Check:**
1. Account types setting in app registration matches your needs
2. Users are in the same tenant (if single tenant)
3. Users have been assigned to the app (if required)

## Security Best Practices

1. **Rotate Secrets Regularly**
   - Set expiration dates on client secrets
   - Rotate before expiration

2. **Use Managed Identity** (Advanced)
   - Consider using Azure Managed Identity instead of client secrets for better security

3. **Restrict Access**
   - Use conditional access policies in Azure AD
   - Restrict to specific IP addresses if needed

4. **Monitor Access**
   - Review sign-in logs in Azure AD
   - Set up alerts for suspicious activity

## Additional Resources

- [Microsoft Identity Platform Documentation](https://docs.microsoft.com/en-us/azure/active-directory/develop/)
- [MSAL Python Documentation](https://msal-python.readthedocs.io/)
- [Azure AD App Registration Guide](https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)
