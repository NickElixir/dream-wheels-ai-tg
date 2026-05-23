import { query } from "@/lib/db";

export type JobStatus = "queued" | "processing" | "completed" | "failed" | string;
export type FeedbackValue = "like" | "dislike" | null;

export type DashboardFilters = {
  status?: string;
  feedback?: string;
  days?: number;
  user?: string;
};

export type SummaryMetric = {
  total: number;
  completed: number;
  failed: number;
  processing: number;
  queued: number;
  likes: number;
  dislikes: number;
  rated: number;
  avgProcessingSeconds: number | null;
};

export type JobsByDay = {
  day: string;
  total: number;
  completed: number;
  failed: number;
};

export type RecentJob = {
  id: string;
  status: JobStatus;
  feedback: FeedbackValue;
  output_image_url: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  processing_seconds: number | null;
  telegram_user_id: string | null;
  username: string | null;
};

type SummaryRow = Record<keyof SummaryMetric, string | number | null>;

function toInt(value: string | number | null | undefined) {
  return Number(value ?? 0);
}

function normalizeFilters(filters: DashboardFilters) {
  const normalizedDays = Number(filters.days || 14);
  const days = [7, 14, 30, 90].includes(normalizedDays) ? normalizedDays : 14;
  const status = filters.status && filters.status !== "all" ? filters.status : null;
  const feedback = filters.feedback && filters.feedback !== "all" ? filters.feedback : null;
  const user = filters.user?.trim().replace(/^@/, "") || null;

  return { days, status, feedback, user };
}

function buildWhere(filters: DashboardFilters) {
  const { days, status, feedback, user } = normalizeFilters(filters);
  const clauses = ["j.created_at >= NOW() - ($1::int * INTERVAL '1 day')"];
  const params: unknown[] = [days];

  if (status) {
    params.push(status);
    clauses.push(`j.status = $${params.length}`);
  }

  if (feedback === "none") {
    clauses.push("j.feedback IS NULL");
  } else if (feedback) {
    params.push(feedback);
    clauses.push(`j.feedback = $${params.length}`);
  }

  if (user) {
    params.push(`%${user}%`);
    clauses.push(
      `EXISTS (
        SELECT 1
        FROM users uf
        WHERE uf.id = j.user_id
          AND (uf.telegram_user_id::text ILIKE $${params.length}
            OR uf.username ILIKE $${params.length})
      )`,
    );
  }

  return {
    days,
    whereSql: clauses.join(" AND "),
    params,
  };
}

export async function getDashboardData(filters: DashboardFilters) {
  const { days, whereSql, params } = buildWhere(filters);

  const [summaryRows, jobsByDay, recentJobs] = await Promise.all([
    query<SummaryRow>(
      `
      SELECT
        COUNT(*)::int AS total,
        COUNT(*) FILTER (WHERE j.status = 'completed')::int AS completed,
        COUNT(*) FILTER (WHERE j.status = 'failed')::int AS failed,
        COUNT(*) FILTER (WHERE j.status = 'processing')::int AS processing,
        COUNT(*) FILTER (WHERE j.status = 'queued')::int AS queued,
        COUNT(*) FILTER (WHERE j.feedback = 'like')::int AS likes,
        COUNT(*) FILTER (WHERE j.feedback = 'dislike')::int AS dislikes,
        COUNT(*) FILTER (WHERE j.feedback IS NOT NULL)::int AS rated,
        ROUND(AVG(EXTRACT(EPOCH FROM (j.completed_at - j.created_at)))
          FILTER (WHERE j.completed_at IS NOT NULL))::int AS "avgProcessingSeconds"
      FROM jobs j
      WHERE ${whereSql}
      `,
      params,
    ),
    query<JobsByDay>(
      `
      SELECT
        TO_CHAR(DATE_TRUNC('day', j.created_at), 'YYYY-MM-DD') AS day,
        COUNT(*)::int AS total,
        COUNT(*) FILTER (WHERE j.status = 'completed')::int AS completed,
        COUNT(*) FILTER (WHERE j.status = 'failed')::int AS failed
      FROM jobs j
      WHERE ${whereSql}
      GROUP BY 1
      ORDER BY 1 ASC
      `,
      params,
    ),
    query<RecentJob>(
      `
      SELECT
        j.id::text,
        j.status,
        j.feedback,
        j.output_image_url,
        j.error_message,
        j.created_at::text,
        j.completed_at::text,
        ROUND(EXTRACT(EPOCH FROM (j.completed_at - j.created_at)))::int
          AS processing_seconds,
        u.telegram_user_id::text,
        u.username
      FROM jobs j
      LEFT JOIN users u ON u.id = j.user_id
      WHERE ${whereSql}
      ORDER BY j.created_at DESC
      LIMIT 50
      `,
      params,
    ),
  ]);

  const row = summaryRows[0] || {};
  const summary: SummaryMetric = {
    total: toInt(row.total),
    completed: toInt(row.completed),
    failed: toInt(row.failed),
    processing: toInt(row.processing),
    queued: toInt(row.queued),
    likes: toInt(row.likes),
    dislikes: toInt(row.dislikes),
    rated: toInt(row.rated),
    avgProcessingSeconds:
      row.avgProcessingSeconds === null || row.avgProcessingSeconds === undefined
        ? null
        : toInt(row.avgProcessingSeconds),
  };

  return { summary, jobsByDay, recentJobs, days };
}
