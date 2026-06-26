import Link from "next/link";
import { getDashboardData } from "@/lib/admin-data";

type SearchParams = Promise<{
  status?: string;
  feedback?: string;
  days?: string;
  user?: string;
}>;

const statusOptions = ["all", "queued", "processing", "completed", "failed"];
const feedbackOptions = ["all", "like", "dislike", "none"];
const dayOptions = [7, 14, 30, 90];

export const dynamic = "force-dynamic";

function formatPercent(part: number, total: number) {
  if (!total) return "0%";
  return `${Math.round((part / total) * 100)}%`;
}

function formatDuration(seconds: number | null) {
  if (seconds === null) return "—";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}m ${rest}s`;
}

function compactId(id: string) {
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

function statusClass(status: string) {
  if (status === "completed") return "border-emerald-800 text-emerald-200";
  if (status === "failed") return "border-red-800 text-red-200";
  if (status === "processing") return "border-amber-800 text-amber-200";
  if (status === "queued") return "border-sky-800 text-sky-200";
  return "border-neutral-700 text-neutral-300";
}

function ledgerEventClass(eventType: string) {
  if (eventType === "purchase_grant" || eventType === "trial_grant") {
    return "border-emerald-800 text-emerald-200";
  }
  if (eventType === "job_reserve") return "border-amber-800 text-amber-200";
  if (eventType === "job_refund") return "border-sky-800 text-sky-200";
  if (eventType === "job_finalize") return "border-neutral-700 text-neutral-300";
  return "border-neutral-700 text-neutral-300";
}

function numberFormat(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function FilterLink({
  label,
  param,
  value,
  current,
  searchParams,
}: {
  label: string;
  param: "status" | "feedback" | "days";
  value: string;
  current: string;
  searchParams: Record<string, string | undefined>;
}) {
  const next = new URLSearchParams();
  for (const [key, existingValue] of Object.entries(searchParams)) {
    if (existingValue) next.set(key, existingValue);
  }
  next.set(param, value);

  return (
    <Link
      className={`rounded border px-3 py-1.5 text-sm transition ${
        current === value
          ? "border-white bg-white text-black"
          : "border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-neutral-500"
      }`}
      href={`/?${next.toString()}`}
    >
      {label}
    </Link>
  );
}

function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="border border-neutral-800 bg-neutral-950 p-4">
      <div className="text-xs uppercase tracking-[0.12em] text-neutral-500">
        {label}
      </div>
      <div className="mt-3 text-3xl font-semibold text-white">{value}</div>
      {sub ? <div className="mt-2 text-sm text-neutral-400">{sub}</div> : null}
    </div>
  );
}

function UserLabel({
  username,
  telegramUserId,
}: {
  username: string | null;
  telegramUserId: string | null;
}) {
  return (
    <div className="flex min-w-32 flex-col gap-1">
      {username ? <span className="font-sans text-sm text-white">@{username}</span> : null}
      <span className="font-mono text-xs text-neutral-500">{telegramUserId || "—"}</span>
    </div>
  );
}

export default async function Home({ searchParams }: { searchParams: SearchParams }) {
  const resolvedSearchParams = await searchParams;
  const status = resolvedSearchParams.status || "all";
  const feedback = resolvedSearchParams.feedback || "all";
  const days = resolvedSearchParams.days || "14";
  const user = resolvedSearchParams.user?.trim() || "";
  const clearUserParams = new URLSearchParams();
  for (const [key, existingValue] of Object.entries(resolvedSearchParams)) {
    if (existingValue && key !== "user") clearUserParams.set(key, existingValue);
  }
  let dashboardData: Awaited<ReturnType<typeof getDashboardData>>;

  try {
    dashboardData = await getDashboardData({
      status,
      feedback,
      days: Number(days),
      user,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown dashboard error";

    return (
      <main className="min-h-screen bg-black text-neutral-100">
        <div className="mx-auto flex max-w-4xl flex-col gap-6 px-5 py-6 sm:px-8">
          <header className="border-b border-neutral-800 pb-5">
            <div className="text-sm text-neutral-500">Dream Wheels AI</div>
            <h1 className="text-3xl font-semibold text-white">Admin Stats</h1>
          </header>
          <section className="border border-red-900 bg-red-950/30 p-5">
            <h2 className="text-lg font-medium text-red-100">Dashboard unavailable</h2>
            <p className="mt-2 text-sm text-red-200">
              Check `DATABASE_URL` and database network access for this deployment.
            </p>
            <pre className="mt-4 overflow-x-auto bg-black p-3 font-mono text-xs text-red-100">
              {message}
            </pre>
          </section>
        </div>
      </main>
    );
  }

  const { summary, jobsByDay, recentJobs, creditLedger } = dashboardData;

  const likeRate = formatPercent(summary.likes, summary.rated);
  const completionRate = formatPercent(summary.completed, summary.total);
  const maxDaily = Math.max(...jobsByDay.map((day) => day.total), 1);

  return (
    <main className="min-h-screen bg-black text-neutral-100">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-5 py-6 sm:px-8">
        <header className="flex flex-col gap-2 border-b border-neutral-800 pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-sm text-neutral-500">Dream Wheels AI</div>
            <h1 className="text-3xl font-semibold text-white">Admin Stats</h1>
          </div>
          <div className="text-sm text-neutral-500">
            Last {days} days
            {user ? ` · User ${user}` : ""} · {new Date().toLocaleString("en-US")}
          </div>
        </header>

        <section className="flex flex-col gap-4 border border-neutral-800 bg-neutral-950 p-4">
          <form className="flex flex-col gap-2 sm:flex-row sm:items-center" action="/">
            <input type="hidden" name="status" value={status} />
            <input type="hidden" name="feedback" value={feedback} />
            <input type="hidden" name="days" value={days} />
            <label className="w-20 text-sm text-neutral-500" htmlFor="user-filter">
              User
            </label>
            <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row">
              <input
                id="user-filter"
                name="user"
                type="search"
                defaultValue={user}
                placeholder="@username or Telegram ID"
                className="min-h-10 min-w-0 flex-1 border border-neutral-700 bg-black px-3 text-sm text-white outline-white placeholder:text-neutral-600"
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  className="min-h-10 border border-white bg-white px-4 text-sm text-black transition hover:bg-neutral-200"
                >
                  Apply
                </button>
                {user ? (
                  <Link
                    className="flex min-h-10 items-center border border-neutral-700 px-4 text-sm text-neutral-300 transition hover:border-neutral-500"
                    href={`/?${clearUserParams.toString()}`}
                  >
                    Clear
                  </Link>
                ) : null}
              </div>
            </div>
          </form>

          <div className="flex flex-wrap items-center gap-2">
            <span className="w-20 text-sm text-neutral-500">Status</span>
            {statusOptions.map((option) => (
              <FilterLink
                key={option}
                label={option}
                param="status"
                value={option}
                current={status}
                searchParams={resolvedSearchParams}
              />
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="w-20 text-sm text-neutral-500">Feedback</span>
            {feedbackOptions.map((option) => (
              <FilterLink
                key={option}
                label={option}
                param="feedback"
                value={option}
                current={feedback}
                searchParams={resolvedSearchParams}
              />
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="w-20 text-sm text-neutral-500">Window</span>
            {dayOptions.map((option) => (
              <FilterLink
                key={option}
                label={`${option}d`}
                param="days"
                value={String(option)}
                current={days}
                searchParams={resolvedSearchParams}
              />
            ))}
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Total jobs"
            value={numberFormat(summary.total)}
            sub={`${completionRate} completed`}
          />
          <MetricCard
            label="Completed"
            value={numberFormat(summary.completed)}
            sub={`${summary.failed} failed`}
          />
          <MetricCard
            label="Feedback"
            value={`${summary.likes} / ${summary.dislikes}`}
            sub={`${likeRate} like rate · ${summary.rated} rated`}
          />
          <MetricCard
            label="Avg generation"
            value={formatDuration(summary.avgProcessingSeconds)}
            sub={`${summary.processing} processing · ${summary.queued} queued`}
          />
        </section>

        <section className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.4fr)]">
          <div className="border border-neutral-800 bg-neutral-950 p-4">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-medium text-white">Jobs By Day</h2>
              <span className="text-sm text-neutral-500">{jobsByDay.length} days</span>
            </div>
            <div className="flex flex-col gap-3">
              {jobsByDay.map((day) => (
                <div key={day.day} className="grid grid-cols-[92px_1fr_54px] items-center gap-3">
                  <div className="font-mono text-xs text-neutral-500">{day.day}</div>
                  <div className="h-3 bg-neutral-900">
                    <div
                      className="h-3 bg-neutral-200"
                      style={{ width: `${Math.max((day.total / maxDaily) * 100, 2)}%` }}
                    />
                  </div>
                  <div className="text-right font-mono text-sm text-white">{day.total}</div>
                </div>
              ))}
              {jobsByDay.length === 0 ? (
                <div className="py-10 text-center text-sm text-neutral-500">
                  No jobs in this window
                </div>
              ) : null}
            </div>
          </div>

          <div className="overflow-hidden border border-neutral-800 bg-neutral-950">
            <div className="flex items-center justify-between border-b border-neutral-800 p-4">
              <h2 className="text-lg font-medium text-white">Recent Jobs</h2>
              <span className="text-sm text-neutral-500">latest 50</span>
            </div>

            <div className="flex flex-col divide-y divide-neutral-900 md:hidden">
              {recentJobs.map((job) => (
                <article key={job.id} className="flex flex-col gap-3 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-mono text-xs text-neutral-500">{compactId(job.id)}</div>
                      <UserLabel username={job.username} telegramUserId={job.telegram_user_id} />
                    </div>
                    <span className={`border px-2 py-1 text-xs ${statusClass(job.status)}`}>
                      {job.status}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-xs uppercase tracking-[0.08em] text-neutral-600">
                        Feedback
                      </div>
                      <div className="mt-1 text-neutral-300">{job.feedback || "—"}</div>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-[0.08em] text-neutral-600">
                        Time
                      </div>
                      <div className="mt-1 font-mono text-neutral-300">
                        {formatDuration(job.processing_seconds)}
                      </div>
                    </div>
                  </div>

                  {job.status === "failed" && job.error_message ? (
                    <div className="border border-red-950 bg-red-950/20 p-3 text-xs text-red-200">
                      {job.error_message}
                    </div>
                  ) : null}

                  <div className="flex items-center justify-between gap-3 text-xs text-neutral-500">
                    <span className="font-mono">{new Date(job.created_at).toLocaleString("en-US")}</span>
                    {job.output_image_url ? (
                      <a
                        className="text-white underline underline-offset-4"
                        href={job.output_image_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        open
                      </a>
                    ) : (
                      <span>—</span>
                    )}
                  </div>
                </article>
              ))}
              {recentJobs.length === 0 ? (
                <div className="py-10 text-center text-sm text-neutral-500">
                  No jobs match the current filters
                </div>
              ) : null}
            </div>

            <div className="hidden overflow-x-auto md:block">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-neutral-900 text-xs uppercase tracking-[0.08em] text-neutral-500">
                  <tr>
                    <th className="px-4 py-3">Job</th>
                    <th className="px-4 py-3">User</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Feedback</th>
                    <th className="px-4 py-3">Time</th>
                    <th className="px-4 py-3">Created</th>
                    <th className="px-4 py-3">Result</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-900">
                  {recentJobs.map((job) => (
                    <tr key={job.id} className="text-neutral-300">
                      <td className="px-4 py-3 font-mono text-xs text-neutral-400">
                        {compactId(job.id)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">
                        <UserLabel username={job.username} telegramUserId={job.telegram_user_id} />
                      </td>
                      <td className="px-4 py-3">
                        <span className={`border px-2 py-1 text-xs ${statusClass(job.status)}`}>
                          {job.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex max-w-64 flex-col gap-1">
                          <span>{job.feedback || "—"}</span>
                          {job.status === "failed" && job.error_message ? (
                            <span className="line-clamp-2 text-xs text-red-300">
                              {job.error_message}
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">
                        {formatDuration(job.processing_seconds)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-neutral-500">
                        {new Date(job.created_at).toLocaleString("en-US")}
                      </td>
                      <td className="px-4 py-3">
                        {job.output_image_url ? (
                          <a
                            className="text-white underline underline-offset-4"
                            href={job.output_image_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            open
                          </a>
                        ) : (
                          <span className="text-neutral-600">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {recentJobs.length === 0 ? (
                    <tr>
                      <td className="px-4 py-10 text-center text-neutral-500" colSpan={7}>
                        No jobs match the current filters
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="overflow-hidden border border-neutral-800 bg-neutral-950">
          <div className="flex flex-col gap-4 border-b border-neutral-800 p-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-medium text-white">Credit Ledger</h2>
              <p className="mt-1 text-sm text-neutral-500">
                Read-only accounting events for purchases, reservations, finalization, and refunds.
              </p>
            </div>
            <span
              className={`w-fit border px-2 py-1 text-xs ${
                creditLedger.available
                  ? "border-emerald-800 text-emerald-200"
                  : "border-amber-800 text-amber-200"
              }`}
            >
              {creditLedger.available ? "connected" : "waiting for credit_ledger table"}
            </span>
          </div>

          <div className="grid gap-3 border-b border-neutral-900 p-4 sm:grid-cols-2 lg:grid-cols-5">
            <MetricCard
              label="Ledger events"
              value={numberFormat(creditLedger.summary.events)}
              sub={`last ${days} days`}
            />
            <MetricCard
              label="Granted"
              value={numberFormat(creditLedger.summary.creditsGranted)}
              sub="purchase + trial"
            />
            <MetricCard
              label="Reserved"
              value={numberFormat(creditLedger.summary.creditsReserved)}
              sub="job_reserve"
            />
            <MetricCard
              label="Finalized"
              value={numberFormat(creditLedger.summary.creditsFinalized)}
              sub="successful jobs"
            />
            <MetricCard
              label="Refunded"
              value={numberFormat(creditLedger.summary.creditsRefunded)}
              sub="technical failure"
            />
          </div>

          {!creditLedger.available ? (
            <div className="p-6 text-sm text-neutral-400">
              Add the `credit_ledger` migration before enabling paid credits. The admin panel will
              start showing ledger events automatically after the table exists.
            </div>
          ) : null}

          {creditLedger.available ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-neutral-900 text-xs uppercase tracking-[0.08em] text-neutral-500">
                  <tr>
                    <th className="px-4 py-3">Event</th>
                    <th className="px-4 py-3">Delta</th>
                    <th className="px-4 py-3">Balance</th>
                    <th className="px-4 py-3">User</th>
                    <th className="px-4 py-3">Job</th>
                    <th className="px-4 py-3">Payment</th>
                    <th className="px-4 py-3">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-900">
                  {creditLedger.recentEvents.map((event) => (
                    <tr key={event.id} className="text-neutral-300">
                      <td className="px-4 py-3">
                        <span
                          className={`whitespace-nowrap border px-2 py-1 text-xs ${ledgerEventClass(
                            event.event_type,
                          )}`}
                        >
                          {event.event_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">
                        {event.credits_delta > 0 ? "+" : ""}
                        {event.credits_delta}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">
                        {event.balance_after ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <UserLabel
                          username={event.username}
                          telegramUserId={event.telegram_user_id}
                        />
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-neutral-500">
                        {event.related_job_id ? compactId(event.related_job_id) : "—"}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-neutral-500">
                        {event.related_payment_id ? compactId(event.related_payment_id) : "—"}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-neutral-500">
                        {new Date(event.created_at).toLocaleString("en-US")}
                      </td>
                    </tr>
                  ))}
                  {creditLedger.recentEvents.length === 0 ? (
                    <tr>
                      <td className="px-4 py-10 text-center text-neutral-500" colSpan={7}>
                        No credit events in this window
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
