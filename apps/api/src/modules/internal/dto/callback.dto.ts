import {
  IsIn,
  IsObject,
  IsOptional,
  IsString,
  IsUUID,
} from 'class-validator';

export class JobStatusCallbackDto {
  @IsUUID()
  jobId!: string;

  @IsIn(['queued', 'running', 'succeeded', 'failed', 'cancelled'])
  status!: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';

  @IsOptional()
  @IsObject()
  result?: Record<string, unknown> | null;

  @IsOptional()
  @IsObject()
  error?: Record<string, unknown> | null;

  @IsOptional()
  @IsString()
  externalTaskId?: string;
}
