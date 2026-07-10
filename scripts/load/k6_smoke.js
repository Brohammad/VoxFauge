import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const errorRate = new Rate('errors');
const sessionLatency = new Trend('session_create_latency', true);
const searchLatency = new Trend('knowledge_search_latency', true);

export const options = {
  vus: 5,
  duration: '30s',
  thresholds: {
    errors: ['rate<0.1'],
    http_req_duration: ['p(95)<2000'],
    session_create_latency: ['p(99)<3000'],
  },
};

const BASE = __ENV.VOXFORGE_BASE_URL || 'http://127.0.0.1:8000';

export default function () {
  const health = http.get(`${BASE}/api/v1/health`);
  check(health, { 'health ok': (r) => r.status === 200 });
  errorRate.add(health.status !== 200);

  const email = `k6-${__VU}-${__ITER}@example.com`;
  const register = http.post(
    `${BASE}/api/v1/auth/register`,
    JSON.stringify({
      email,
      password: 'securepass123',
      full_name: 'K6 User',
      org_name: 'K6 Org',
    }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(register, { 'register ok': (r) => r.status === 201 });
  errorRate.add(register.status !== 201);
  if (register.status !== 201) {
    sleep(1);
    return;
  }

  const token = register.json('tokens.access_token');
  const headers = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  const sessionStart = Date.now();
  const session = http.post(`${BASE}/api/v1/sessions`, '{}', { headers });
  sessionLatency.add(Date.now() - sessionStart);
  check(session, { 'session created': (r) => r.status === 201 });
  errorRate.add(session.status !== 201);

  const searchStart = Date.now();
  const search = http.post(
    `${BASE}/api/v1/knowledge/search`,
    JSON.stringify({ query: 'support policy', limit: 3, min_similarity: 0 }),
    { headers },
  );
  searchLatency.add(Date.now() - searchStart);
  check(search, { 'search ok': (r) => r.status === 200 });
  errorRate.add(search.status !== 200);

  sleep(0.5);
}
