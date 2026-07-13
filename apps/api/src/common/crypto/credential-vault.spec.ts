import { randomBytes } from 'crypto';
import { AppConfig } from '@/config/app-config';
import { CredentialVault } from './credential-vault';

function vault(): CredentialVault {
  const config = {
    API_CREDENTIAL_KEY: randomBytes(32).toString('base64'),
  } as AppConfig;
  return new CredentialVault(config);
}

describe('CredentialVault', () => {
  it('round-trips a secret', () => {
    const v = vault();
    const secret = 'ghp_deadbeefdeadbeefdeadbeef';
    expect(v.decrypt(v.encrypt(secret))).toBe(secret);
  });

  it('produces distinct ciphertexts for the same input (random IV)', () => {
    const v = vault();
    expect(v.encrypt('same')).not.toBe(v.encrypt('same'));
  });

  it('rejects tampered ciphertext (auth tag)', () => {
    const v = vault();
    const ct = v.encrypt('secret');
    const parts = ct.split('.');
    parts[3] = Buffer.from('tampered').toString('base64url');
    expect(() => v.decrypt(parts.join('.'))).toThrow();
  });

  it('rejects malformed input', () => {
    expect(() => vault().decrypt('not-valid')).toThrow('Malformed ciphertext');
  });
});
