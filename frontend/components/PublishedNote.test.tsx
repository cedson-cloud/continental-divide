import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PublishedNote } from "./PublishedNote";

afterEach(cleanup);

describe("PublishedNote", () => {
  it("links to the tracking plan the approved event joined", () => {
    render(<PublishedNote hasSnippets={false} />);
    expect(screen.getByRole("link", { name: "tracking plan" })).toHaveAttribute(
      "href",
      "/catalog",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Done. This is now in the tracking plan.",
    );
  });

  it("points engineers to their code only when there is code to show", () => {
    render(<PublishedNote hasSnippets />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "engineers have the code to send it under For engineers below.",
    );
  });
});
