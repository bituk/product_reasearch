"""
MCP server exposing the Creative Research Report as a tool.
Run with: uv run --with mcp creative_research/mcp_server.py
Or: python -m creative_research.mcp_server
"""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from creative_research.report_generator import generate_report

mcp = FastMCP(
    "Creative Research Report",
    json_response=True,
)


@mcp.tool()
def generate_creative_research_report(
    product_link: str,
    output_path: str | None = None,
    model: str = "gpt-4o",
) -> str:
    """Generate a full Creative Agency Research Report from a product URL.

    Fetches the product page, then uses an LLM to produce a structured report including:
    - Report cover and product summary
    - Step 1: Videos analysis (hashtags, video scrape strategy, competitors, ad library links, organic concepts)
    - Step 2: Comments analysis (scrape strategy, thematic clusters, verbatim comment banks)
    - Step 3: Avatar angles (10 avatars, top 10 selling points, 10 core desires, 10 pain problems)

    Args:
        product_link: Full URL of the product (e.g. Amazon, brand site, Shopify).
        output_path: Optional path to save the report Markdown file. If not set, report is returned as text.
        model: OpenAI model to use (default: gpt-4o).

    Returns:
        The full report in Markdown, or a message that the report was saved to output_path.
    """
    if not product_link or not product_link.strip():
        return "Error: product_link is required and cannot be empty."

    try:
        report = generate_report(
            product_link.strip(),
            product_page_content=None,
            model=model,
        )
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error generating report: {e}"

    if output_path and output_path.strip():
        path = Path(output_path.strip())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
        return f"Report saved to {path.absolute()} ({len(report)} characters)."

    return report


@mcp.resource("creative-research://outline")
def get_outline() -> str:
    """Return the Creative Research Report outline (structure and section descriptions)."""
    outline_path = Path(__file__).resolve().parent.parent / "CREATIVE_RESEARCH_REPORT_OUTLINE.md"
    if outline_path.exists():
        return outline_path.read_text(encoding="utf-8")
    return "Outline file not found."


@mcp.prompt()
def research_report_prompt(product_link: str) -> str:
    """Prompt template to generate a Creative Research Report for a product.

    Use this with an LLM or the generate_creative_research_report tool.
    """
    return (
        f"Generate a full Creative Agency Research Report for this product: {product_link}\n\n"
        "Use the tool generate_creative_research_report with this product_link to get "
        "the complete report (videos analysis, comments analysis, avatars, selling points, "
        "desires, pain points). Alternatively, follow the outline in the creative-research://outline resource."
    )


if __name__ == "__main__":
    # Default: stdio for Cursor/Claude Desktop; use CREATIVE_RESEARCH_MCP_HTTP=1 for HTTP
    if os.environ.get("CREATIVE_RESEARCH_MCP_HTTP"):
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
