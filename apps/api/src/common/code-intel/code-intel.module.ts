import { Global, Module } from '@nestjs/common';
import { CodeIntelClient } from './code-intel.client';

@Global()
@Module({
  providers: [CodeIntelClient],
  exports: [CodeIntelClient],
})
export class CodeIntelModule {}
