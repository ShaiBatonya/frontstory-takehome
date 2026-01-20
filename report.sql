WITH cost_utc AS (
  SELECT
    date_trunc(
      'day',
      (to_timestamp(data_date, 'MM/DD/YY HH24:MI') AT TIME ZONE 'America/New_York')
    ) AS date_utc,
    campaign_id,
    MIN(campaign_name) AS campaign_name,
    SUM(clicks)::numeric AS total_clicks,
    SUM(cost)::numeric AS total_cost
  FROM cost_report
  GROUP BY 1, 2
),
rev_utc AS (
  SELECT
    date_trunc(
      'day',
      (to_timestamp(data_date, 'MM/DD/YY HH24:MI') AT TIME ZONE 'America/New_York')
    ) AS date_utc,
    campaign_id,
    SUM(revenue)::numeric AS total_revenue
  FROM revenue_report
  GROUP BY 1, 2
),
joined AS (
  SELECT
    COALESCE(c.date_utc, r.date_utc) AS date_utc,
    COALESCE(c.campaign_id, r.campaign_id) AS campaign_id,
    COALESCE(c.campaign_name, '') AS campaign_name,
    COALESCE(r.total_revenue, 0) AS total_revenue,
    COALESCE(c.total_cost, 0) AS total_cost,
    COALESCE(c.total_clicks, 0) AS total_clicks
  FROM cost_utc c
  FULL OUTER JOIN rev_utc r
    ON c.date_utc = r.date_utc AND c.campaign_id = r.campaign_id
)
SELECT
  to_char(date_utc, 'YYYY/MM/DD') AS date,
  campaign_id,
  campaign_name,
  total_revenue,
  total_cost,
  (total_revenue - total_cost) AS total_profit,
  total_clicks,
  CASE
    WHEN total_clicks = 0 OR total_cost = 0 THEN NULL
    ELSE (total_revenue / total_clicks) / (total_cost / total_clicks)
  END AS total_roi,
  CASE
    WHEN total_clicks = 0 THEN NULL
    ELSE total_cost / total_clicks
  END AS avg_cpc
FROM joined
WHERE date_utc >= :date_from::date
  AND date_utc <= :date_to::date
ORDER BY date, campaign_id;
