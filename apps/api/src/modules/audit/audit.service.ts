import { Inject, Injectable, Logger } from '@nestjs/common';
import { uuidv7 } from 'uuidv7';
import { Database, DB } from '@/database/database.module';
import { auditLog } from '@/database/schema';

export interface AuditEntry {
  orgId: string;
  actorType: 'user' | 'api_key' | 'agent' | 'system';
  actorId: string;
  action: string;
  resourceType: string;
  resourceId?: string;
  metadata?: Record<string, unknown>;
}

@Injectable()
export class AuditService {
  private readonly logger = new Logger(AuditService.name);

  constructor(@Inject(DB) private readonly db: Database) {}

  /**
   * Best-effort append: an audit failure must never fail the user's request,
   * but it must never be silent either.
   */
  async record(entry: AuditEntry): Promise<void> {
    try {
      await this.db.insert(auditLog).values({
        id: uuidv7(),
        orgId: entry.orgId,
        actorType: entry.actorType,
        actorId: entry.actorId,
        action: entry.action,
        resourceType: entry.resourceType,
        resourceId: entry.resourceId,
        metadata: entry.metadata ?? {},
      });
    } catch (err) {
      this.logger.error(
        { err, action: entry.action },
        'failed to write audit entry',
      );
    }
  }
}
