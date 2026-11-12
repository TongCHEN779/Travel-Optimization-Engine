const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
export default { reactStrictMode: true, output: "export", basePath: base, images: { unoptimized: true }, trailingSlash: true };
