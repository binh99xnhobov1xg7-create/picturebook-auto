"""截取运行中的网页首页（输入表单 + 步骤条），给分享 PPT 用。"""
import asyncio
from pathlib import Path

OUT = Path(r"C:\Users\Jered\picturebook-auto\outputs\_ppt_assets")
OUT.mkdir(parents=True, exist_ok=True)


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1500, "height": 1400},
                                            device_scale_factor=2)
        page = await context.new_page()
        await page.goto("http://localhost:8501", wait_until="networkidle", timeout=40000)
        await asyncio.sleep(4)
        # 顶部视口截图（表单 + 步骤条）
        await page.screenshot(path=str(OUT / "webapp_landing.png"), full_page=False)
        print("saved webapp_landing.png")
        # 整页截图（备用）
        await page.screenshot(path=str(OUT / "webapp_fullpage.png"), full_page=True)
        print("saved webapp_fullpage.png")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
