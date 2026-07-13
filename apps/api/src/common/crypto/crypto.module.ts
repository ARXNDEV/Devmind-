import { Global, Module } from '@nestjs/common';
import { CredentialVault } from './credential-vault';

@Global()
@Module({
  providers: [CredentialVault],
  exports: [CredentialVault],
})
export class CryptoModule {}
