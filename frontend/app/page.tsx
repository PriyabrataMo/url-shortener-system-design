"use client";

import { FormEvent, useState } from "react";
import { ArrowUpRight, Check, Copy, Link2, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const API_URL = process.env.NEXT_PUBLIC_API_URL;
if (!API_URL) {
  throw new Error("NEXT_PUBLIC_API_URL is required. Create frontend/.env.local.");
}

type ShortUrl = {
  code: string;
  long_url: string;
  short_url: string;
};

export default function Home() {
  const [longUrl, setLongUrl] = useState("");
  const [result, setResult] = useState<ShortUrl | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  async function createShortUrl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setResult(null);
    setCopied(false);
    setIsLoading(true);

    console.log("[URL SHORTENER REQUEST]", {
      apiUrl: API_URL,
      origin: window.location.origin,
      longUrl,
    });

    const response = await fetch(`${API_URL}/api/urls`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ long_url: longUrl }),
    });
    const data = await response.json();
    console.log("[URL SHORTENER RESPONSE]", response.status, data);
    if (!response.ok) throw new Error(data.error);
    setResult(data);
    setIsLoading(false);
  }

  async function copyShortUrl() {
    if (!result) return;
    await navigator.clipboard.writeText(result.short_url);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <main className="min-h-screen px-6 py-12 sm:py-20">
      <div className="mx-auto max-w-2xl">
        <div className="mb-10 text-center">
          <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-950 text-white">
            <Link2 size={23} />
          </div>
          <p className="mb-3 text-sm font-medium uppercase tracking-[0.2em] text-slate-500">System Design Lab</p>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">Make a link tiny.</h1>
          <p className="mx-auto mt-4 max-w-lg text-base leading-7 text-slate-600">
            A small, friendly URL shortener. The UI talks to Flask, Flask stores the mapping, and the redirect path stays simple.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Shorten a long URL</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={createShortUrl} className="space-y-4">
              <Input
                type="url"
                required
                value={longUrl}
                onChange={(event) => setLongUrl(event.target.value)}
                placeholder="https://example.com/your-long-link"
                aria-label="Long URL"
              />
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? <Loader2 className="mr-2 animate-spin" size={17} /> : <Link2 className="mr-2" size={17} />}
                {isLoading ? "Creating..." : "Create short URL"}
              </Button>
            </form>

            {error && <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}

            {result && (
              <div className="mt-6 rounded-2xl bg-slate-50 p-4">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Your short URL</p>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <a className="break-all text-lg font-semibold text-slate-950 underline decoration-slate-300 underline-offset-4" href={result.short_url} target="_blank" rel="noreferrer">
                    {result.short_url}
                  </a>
                  <div className="flex shrink-0 gap-2">
                    <Button variant="outline" size="sm" onClick={copyShortUrl}>
                      {copied ? <Check size={15} /> : <Copy size={15} />}
                      <span className="ml-2">{copied ? "Copied" : "Copy"}</span>
                    </Button>
                    <Button size="sm" onClick={() => window.open(result.short_url, "_blank")}>
                      <ArrowUpRight size={15} />
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-sm text-slate-500">Try the redirect, then inspect the API response and database record.</p>
      </div>
    </main>
  );
}
