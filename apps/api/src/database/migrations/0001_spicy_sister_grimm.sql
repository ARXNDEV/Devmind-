CREATE TYPE "product"."repo_index_status" AS ENUM('pending', 'indexing', 'ready', 'failed', 'stale');--> statement-breakpoint
CREATE TYPE "product"."repo_provider" AS ENUM('github', 'gitlab', 'bitbucket', 'generic_git', 'local');--> statement-breakpoint
CREATE TABLE "product"."repositories" (
	"id" uuid PRIMARY KEY NOT NULL,
	"org_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"name" text NOT NULL,
	"provider" "product"."repo_provider" NOT NULL,
	"clone_url" text NOT NULL,
	"default_branch" text DEFAULT 'main' NOT NULL,
	"encrypted_credentials" text,
	"indexed_commit_sha" text,
	"index_status" "product"."repo_index_status" DEFAULT 'pending' NOT NULL,
	"last_indexed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "product"."repositories" ADD CONSTRAINT "repositories_org_id_organizations_id_fk" FOREIGN KEY ("org_id") REFERENCES "product"."organizations"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "product"."repositories" ADD CONSTRAINT "repositories_project_id_projects_id_fk" FOREIGN KEY ("project_id") REFERENCES "product"."projects"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "repositories_project_idx" ON "product"."repositories" USING btree ("project_id");