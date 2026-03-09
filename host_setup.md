# Hosting CCTV & Infra Scanner Pro on Cloudflare

Cloudflare Tunnels provide a way to securely expose your local dashboard to the internet without opening any ports on your router.

## 🚀 Quick Setup (Transient Tunnel)

The updated `CCTV_Scanner.bat` has a built-in option to launch a quick tunnel. 

1.  **Download Cloudflared**: Download the `cloudflared-windows-amd64.msi` from [Cloudflare's GitHub Releases](https://github.com/cloudflare/cloudflared/releases) and install it.
2.  **Run the Batch File**: Run `CCTV_Scanner.bat` as Administrator.
3.  **Select Option 2**: Choose "Enable Remote Access".
4.  **Copy the Link**: A new window will open with a link ending in `.trycloudflare.com`. Copy this and use it on your mobile device or external PC.

## 💎 Permanent Setup (Custom Domain)

To use a custom domain (e.g., `scanner.yourdomain.com`), follow these steps:

1.  **Install & Login**:
    ```cmd
    cloudflared tunnel login
    ```
2.  **Create a Tunnel**:
    ```cmd
    cloudflared tunnel create cctv-scanner
    ```
3.  **Configure**: Create a `config.yml` in your `cloudflared` directory:
    ```yaml
    url: http://localhost:5001
    tunnel: <YOUR-TUNNEL-ID>
    credentials-file: <PATH-TO-CREDENTIALS-JSON>
    ```
4.  **Route DNS**:
    ```cmd
    cloudflared tunnel route dns cctv-scanner scanner.yourdomain.com
    ```
5.  **Run as Service**:
    ```cmd
    cloudflared service install
    ```

## 🔒 Security Note
When hosting publicly, ensure you are in a safe environment. The current dashboard does not have a login screen. **Do not share your public URL with unauthorized parties.**
