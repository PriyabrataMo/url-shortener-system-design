import http from "k6/http";
import { check } from "k6";

const target = __ENV.TARGET_URL;

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURATION || "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<200"],
  },
};

export function setup() {
  const response = http.post(
    `${target}/api/urls`,
    JSON.stringify({ long_url: "https://www.youtube.com/" }),
    { headers: { "Content-Type": "application/json" } },
  );

  check(response, { "create returned 201": (result) => result.status === 201 });
  return response.json("code");
}

export default function (code) {
  const response = http.get(`${target}/r/${code}`, { redirects: 0 });

  check(response, {
    "redirect returned 302": (result) => result.status === 302,
    "redirect has location": (result) => Boolean(result.headers.Location),
  });
}
