import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Medero", short_name: "Medero", start_url: "/", display: "standalone",
    background_color: "#f3f7fb", theme_color: "#1a6fc4",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
