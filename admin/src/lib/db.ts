import { Pool, type QueryResultRow } from "pg";

let pool: Pool | null = null;

export function getPool() {
  const connectionString = process.env.DATABASE_URL;

  if (!connectionString) {
    throw new Error("DATABASE_URL is not configured");
  }

  if (!pool) {
    pool = new Pool({
      connectionString,
      max: 3,
      ssl: connectionString.includes("localhost")
        ? false
        : { rejectUnauthorized: false },
    });
  }

  return pool;
}

export async function query<T extends QueryResultRow>(
  sql: string,
  params: unknown[] = [],
) {
  const result = await getPool().query<T>(sql, params);
  return result.rows;
}
