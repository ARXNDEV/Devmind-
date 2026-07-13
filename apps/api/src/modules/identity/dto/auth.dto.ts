import {
  IsEmail,
  IsString,
  Matches,
  MaxLength,
  MinLength,
} from 'class-validator';

export class RegisterDto {
  @IsString()
  @MinLength(2)
  @MaxLength(120)
  organizationName!: string;

  @IsString()
  @MinLength(1)
  @MaxLength(120)
  name!: string;

  @IsEmail()
  @MaxLength(254)
  email!: string;

  /** OWASP ASVS: length is the primary strength control. */
  @IsString()
  @MinLength(12)
  @MaxLength(128)
  @Matches(/^\S(.*\S)?$/, { message: 'password must not start or end with whitespace' })
  password!: string;
}

export class LoginDto {
  @IsEmail()
  @MaxLength(254)
  email!: string;

  @IsString()
  @MinLength(1)
  @MaxLength(128)
  password!: string;
}

export class AuthUserDto {
  id!: string;
  email!: string;
  name!: string;
  role!: string;
}

export class AuthOrgDto {
  id!: string;
  name!: string;
  slug!: string;
}

export class AuthResponseDto {
  accessToken!: string;
  /** Seconds until access token expiry. */
  expiresIn!: number;
  user!: AuthUserDto;
  organization!: AuthOrgDto;
}
