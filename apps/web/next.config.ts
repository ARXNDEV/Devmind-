import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle consumed by the Docker runtime stage.
  output: "standalone",
  poweredByHeader: false,

  // Proxy API calls through the web server's own origin. The browser uses
  // relative URLs (no CORS, no baked absolute host), and the Next server
  // forwards to the api service over the internal network. Works identically
  // for direct access, an SSH tunnel, or a future TLS reverse proxy.
  // API_PROXY_TARGET is a server-side (runtime) env, not baked into the bundle.
  async rewrites() {
    const target = process.env.API_PROXY_TARGET ?? "http://api:4000";
    return [{ source: "/api/:path*", destination: `${target}/api/:path*` }];
  },
};

export default nextConfig;
