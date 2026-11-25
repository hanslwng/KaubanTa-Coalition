function publicKey() {
  const key = String(process.env.SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || "");
  if (key.startsWith("sb_secret_")) return "";
  return key;
}

module.exports = function handler(req, res) {
  const url = String(process.env.SUPABASE_URL || "").replace(/\/$/, "");
  const key = publicKey();
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Content-Type", "application/json");
  res.status(200).json({
    url,
    key,
    configured: url.startsWith("https://") && key.length > 20
  });
};
