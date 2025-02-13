import { LocalStorage } from '../utils/local_storage'
import { Logger } from '../utils/logger';


export class GoogleOAuth {
    private clientId: string;
    private redirectUri: string;
    private scopes: string;
    private authUrl: string;
    private localStorage: LocalStorage;
    private accessToken: string;
    private expirationTime: number;
    private logger: Logger;

    constructor(
        clientId: string,
        scopes: string,
        app: string
    ) {
        this.clientId = `${clientId}.apps.googleusercontent.com`
        this.redirectUri = `https://${chrome.runtime.id}.chromiumapp.org/`;
        this.scopes = scopes;
        this.authUrl = `https://accounts.google.com/o/oauth2/v2/auth`+
                       `?client_id=${this.clientId}`+
                       `&redirect_uri=${this.redirectUri}`+
                       `&response_type=token&scope=${this.scopes}`+
                       `&prompt=select_account&hd=speakcare.ai`;
        this.localStorage = new LocalStorage(`GoogleOAuth:${app}`);
        this.logger = new Logger(`GoogleOAuth:${app}`);
        this.accessToken = '';
        this.expirationTime = 0;
    }

    async init() {
        const items = await this.localStorage.getItems(['accessToken', 'expirationTime']);
        if (items) {
            this.accessToken = items.accessToken;
            this.expirationTime = items.expirationTime;
        }
    }

    async isTokenValid(): Promise<boolean> {

        if (!this.accessToken) {
            this.logger.info("Access token not found.");
            return false;
        }
        else if (Date.now() >= this.expirationTime) {
            this.logger.info("Access token expired.");
            return false;
        }
        else {
            try {
                const response = await fetch(`https://oauth2.googleapis.com/tokeninfo?access_token=${this.accessToken}`);
                
                if (response.ok) {
                    this.logger.info("Token is valid.");
                    return true;
                } else {
                    this.logger.info("Token is invalid or expired.");
                    return false;
                }
              } catch (error) {
                this.logger.error("Error validating token:", error);
                return false;
              }
        }
    }

    getAccessToken() {
        return this.accessToken;
    }

    async authenticate() {
        return new Promise<void>((resolve, reject) => {
          chrome.identity.launchWebAuthFlow(
            {
              url: this.authUrl,
              interactive: true
            },
            (redirectUrl) => {
              if (chrome.runtime.lastError) {
                this.logger.error("Authentication failed:", chrome.runtime.lastError);
                reject(new Error(chrome.runtime.lastError.message));
                return;
              }
      
              if (!redirectUrl) {
                this.logger.error("Redirect URL is undefined.");
                reject(new Error("Redirect URL is undefined."));
                return;
              }
      
              const params = new URLSearchParams(new URL(redirectUrl).hash.substring(1));
              this.accessToken = params.get('access_token') || '';
              const expiresIn = parseInt(params.get('expires_in') || '3600', 10);  // Default to 1 hour if not provided
              const expirationTime = Date.now() + expiresIn * 1000;  // Convert to milliseconds
      
              if (this.accessToken) {
                // Store the token and expiration time in chrome.storage
                this.localStorage.setItems({ accessToken: this.accessToken, expirationTime: expirationTime });
                this.logger.info("Token stored successfully.");
                resolve();
              } else {
                this.logger.error("Access token not found in redirect URL.");
                reject(new Error("Access token not found in redirect URL."));
              }
            }
          );
        });
    }
}
  