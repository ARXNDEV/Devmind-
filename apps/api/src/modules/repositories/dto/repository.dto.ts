import {
  IsEnum,
  IsOptional,
  IsString,
  MaxLength,
  MinLength,
} from 'class-validator';

export const REPO_PROVIDERS = [
  'github',
  'gitlab',
  'bitbucket',
  'generic_git',
  'local',
] as const;
export type RepoProvider = (typeof REPO_PROVIDERS)[number];

export class CreateRepositoryDto {
  @IsString()
  @MinLength(1)
  @MaxLength(120)
  name!: string;

  @IsEnum(REPO_PROVIDERS)
  provider!: RepoProvider;

  /** Clone URL, or an absolute path when provider is `local`. */
  @IsString()
  @MinLength(1)
  @MaxLength(2048)
  cloneUrl!: string;

  @IsOptional()
  @IsString()
  @MaxLength(255)
  defaultBranch?: string;

  /** Write-only: encrypted at rest, never returned. */
  @IsOptional()
  @IsString()
  @MaxLength(4096)
  credentials?: string;
}

export class RepositoryDto {
  id!: string;
  name!: string;
  provider!: RepoProvider;
  cloneUrl!: string;
  defaultBranch!: string;
  indexStatus!: string;
  indexedCommitSha!: string | null;
  hasCredentials!: boolean;
  lastIndexedAt!: Date | null;
  createdAt!: Date;
}
