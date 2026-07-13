import { Inject, Injectable } from '@nestjs/common';
import {
  createCipheriv,
  createDecipheriv,
  randomBytes,
} from 'crypto';
import { APP_CONFIG, AppConfig } from '@/config/app-config';

/**
 * Encrypts integration credentials at rest with AES-256-GCM (08-security.md).
 *
 * This is the env-key-backed adapter for a `CredentialVault` port; a KMS/Vault
 * adapter replaces it in production without touching callers. Ciphertext format
 * is `v1.<iv>.<authTag>.<data>`, all base64url — versioned so the scheme can
 * evolve.
 */
@Injectable()
export class CredentialVault {
  private readonly key: Buffer;

  constructor(@Inject(APP_CONFIG) config: AppConfig) {
    this.key = Buffer.from(config.API_CREDENTIAL_KEY, 'base64');
  }

  encrypt(plaintext: string): string {
    const iv = randomBytes(12);
    const cipher = createCipheriv('aes-256-gcm', this.key, iv);
    const data = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()]);
    const tag = cipher.getAuthTag();
    return [
      'v1',
      iv.toString('base64url'),
      tag.toString('base64url'),
      data.toString('base64url'),
    ].join('.');
  }

  decrypt(ciphertext: string): string {
    const [version, ivB64, tagB64, dataB64] = ciphertext.split('.');
    if (version !== 'v1' || !ivB64 || !tagB64 || !dataB64) {
      throw new Error('Malformed ciphertext');
    }
    const decipher = createDecipheriv(
      'aes-256-gcm',
      this.key,
      Buffer.from(ivB64, 'base64url'),
    );
    decipher.setAuthTag(Buffer.from(tagB64, 'base64url'));
    return Buffer.concat([
      decipher.update(Buffer.from(dataB64, 'base64url')),
      decipher.final(),
    ]).toString('utf8');
  }
}
