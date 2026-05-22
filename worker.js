export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const target = env.BACKEND + url.pathname + url.search;

    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    }

    const response = await fetch(target);
    const newRes = new Response(response.body, response);
    newRes.headers.set("Access-Control-Allow-Origin", "*");
    return newRes;
  },
};
