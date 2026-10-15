import { readFileSync } from "fs";
import path from "path";
import { describe, expect, it, vi } from "vitest";
import { SITE_URL } from "@/lib/demo";
import { metadata } from "./layout";

vi.mock("next/font/google", () => ({
  Instrument_Sans: () => ({ variable: "font-sans" }),
  JetBrains_Mono: () => ({ variable: "font-mono" }),
}));

// A PNG's width and height are the first two fields of its IHDR chunk.
function pngSize(file: string): { width: number; height: number } {
  const bytes = readFileSync(file);
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

describe("the link preview", () => {
  it("resolves against the live site, so a preview never points at a deployment's own address", () => {
    expect(SITE_URL).toMatch(/^https:\/\//);
    expect(String(metadata.metadataBase)).toBe(`${SITE_URL}/`);
  });

  it("is a 1200 by 630 image, the size link previews crop to", () => {
    expect(pngSize(path.resolve(__dirname, "opengraph-image.png"))).toEqual({
      width: 1200,
      height: 630,
    });
  });

  it("has alt text", () => {
    const alt = readFileSync(path.resolve(__dirname, "opengraph-image.alt.txt"), "utf8").trim();
    expect(alt.length).toBeGreaterThan(20);
    expect(alt).not.toContain("\n");
  });
});
