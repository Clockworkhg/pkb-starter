"""
批量下载CNKI中文论文PDF（通过中传图书馆VPN）
从文献地图中提取论文列表，逐个下载PDF到 raw/papers/cnki-20250621/
"""
import requests
import time
import os
import re
from pathlib import Path

# === 配置 ===
SAVE_DIR = Path(r"D:\PKB_个人知识库\raw\papers\cnki-20250621")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# 从浏览器提取的 cookies
COOKIES = {
    "Ecp_ClientId": "__sBHYZg__U8JhJDSty0V1SHizzeB7WU0VNCjoCE48",
    "Ecp_LoginStuts": '{"IsAutoLogin":true,"UserName":"DX0544","ShowName":"%E4%B8%AD%E5%9B%BD%E4%BC%A0%E5%AA%92%E5%A4%A7%E5%AD%A6","UserType":"bk","BUserName":"","BShowName":"","BUserType":"","r":"Jb6Hwu","Members":[]}',
    "Ecp_session": "1",
    "SID_kns_new": "kns2618132",
    "LID": "WEEvREcwSlJHSldSdmVpbEs1YkxQcHMzTGNjT1hGNExWNzEwUFpwbUo1bz0=$9A4hF_YAuvQ5obgVAqNKPCYcEjKensW4IQMovwHtwkF4VYPoHbKxJw!!",
    "c_m_LinID": "LinID=WEEvREcwSlJHSldSdmVpbEs1YkxQcHMzTGNjT1hGNExWNzEwUFpwbUo1bz0=$9A4hF_YAuvQ5obgVAqNKPCYcEjKensW4IQMovwHtwkF4VYPoHbKxJw!!&ot=06%2F21%2F2026%2018%3A59%3A04",
}

# VPN 基础URL (中传图书馆)
VPN_BASE = "https://elib.cuc.edu.cn/https/vpn/1/NNYHGLUDN3WXTLUPMW4A"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": f"{VPN_BASE}/kns8s/defaultresult/index",
}

session = requests.Session()
session.cookies.update(COOKIES)
session.headers.update(HEADERS)


def get_pdf_url(abstract_url: str) -> str | None:
    """从知网摘要页提取PDF下载链接"""
    try:
        resp = session.get(abstract_url, timeout=30, allow_redirects=True)
        resp.encoding = 'utf-8'

        # 检查是否需要验证码
        if '拖动下方拼图' in resp.text or 'captcha' in resp.text.lower():
            print(f"  ⚠️ 需要验证码，跳过")
            return None

        # 查找PDF下载链接
        # CNKI PDF下载链接格式: /bar/download/order?id=...
        pdf_match = re.search(r'https://[^"\']+/bar/download/order\?id=[^"\']+', resp.text)
        if pdf_match:
            return pdf_match.group(0)

        # 备用：查找 btn-dlpdf 的父链接
        pdf_match2 = re.search(r'<li class="btn-dlpdf"[^>]*>.*?href="([^"]+)"', resp.text, re.DOTALL)
        if pdf_match2:
            return pdf_match2.group(1)

        print(f"  ⚠️ 未找到PDF下载链接")
        return None
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return None


def download_pdf(pdf_url: str, filename: str) -> bool:
    """下载PDF文件"""
    try:
        resp = session.get(pdf_url, timeout=60, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 10000:
            filepath = SAVE_DIR / filename
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            print(f"  ✅ 已保存: {filename} ({len(resp.content)//1024}KB)")
            return True
        else:
            print(f"  ❌ 下载失败: HTTP {resp.status_code}, size={len(resp.content)}")
            return False
    except Exception as e:
        print(f"  ❌ 下载异常: {e}")
        return False


# === 论文列表（文献地图第一梯队 + CNKI已验证论文）===
PAPERS = [
    # === 第一梯队：贺雪峰核心论文 ===
    {
        "title": "迈向村社养老：农村老龄化问题应对模式比较与优化路径",
        "abstract_url": f"{VPN_BASE}/kcms2/article/abstract?v=lcJiu7QxtGMezT1avah-bok9h-07hRGF3VhGAbSjHglWVnRMjgdEvauHmVzBmhy5UTrFEUGCd4kXGML6KTep-Yty-9n3Q6Jlcienf0ivdLQ5MmC2gbBkIhfEGSyMiQOpa_FvcUOEzbSaFpWi8q7TteWviYek2j9dXgH69qlUgV-6pwB151hDCg&uniplatform=NZKPT&language=CHS",
        "filename": "任亮亮_贺雪峰_2025_迈向村社养老.pdf",
    },
    {
        "title": "村社养老实践与国家责任",
        "abstract_url": f"{VPN_BASE}/kcms2/article/abstract?v=lcJiu7QxtGO29QiDLrveQk5UIz7C0hMAII8kYzPrO3H5l3A1Wg6FXI_jIL8JfKgHypl7YZwGq_vCy23G9D3WmElFEkhyKjba_vEuPnsrfORhORfRW_-WCmek6qYkh-9geN2UGDZRkmPnP48LXhW8ujwSGxk9ygZOgRKheV0WNpT7vNpvQoFk8g==&uniplatform=NZKPT&language=CHS",
        "filename": "贺雪峰_2025_村社养老实践与国家责任.pdf",
    },
    {
        "title": "村庄空心化与适度村级治理",
        "abstract_url": f"{VPN_BASE}/kcms2/article/abstract?v=lcJiu7QxtGNI2EudibMiw7s81NEcy_qevYzA36KZe-0pozUv9-uN7r25TdkeNkqo-LLvHzma7CNgRztBnanTFSXidzv8PWMZ1LqOAFK-aWuiQhyHcrrArs9RDtY1FUpkgq2Dy34Dt_M86VCG4vDonwAPyVZ8LVstFiiWSp-wSkoSpUX4_L15lg==&uniplatform=NZKPT&language=CHS",
        "filename": "贺雪峰_2025_村庄空心化与适度村级治理.pdf",
    },
    {
        "title": "乡村何以德治？——农民行为逻辑的社会学分析",
        "abstract_url": f"{VPN_BASE}/kcms2/article/abstract?v=lcJiu7QxtGO3qCLBmZL2EEmTJpzCho94eLEIK_lsh86IxsOsII25Uh0iiq1hvmdEh68FZcw2PeSqpdrvgB3OIOQWTqL8cB7ZbUBkqe0_EVF52ylwtVQKTU4phuev6JSV1GROPp6Fb9fYOKnrQyv6oi-oIL4hxt5L7BDO5CsHU9wtDGHToARHOw==&uniplatform=NZKPT&language=CHS",
        "filename": "桂华_贺雪峰_2026_乡村何以德治.pdf",
    },
    {
        "title": "走向群众自觉行动的基层治理实践",
        "abstract_url": f"{VPN_BASE}/kcms2/article/abstract?v=lcJiu7QxtGN1oG9jQtfMlK2ydD3We5zwriTt0npeiuenHL39QWcZl0rEUl7b4bwYH3sDpFpcn9amQkqlLJKhM1lFg8SAEJ--wZSYZ_IXd9_f8YMuTE-PHUACSrZYnr5_SC3P9fi1vCa2GqxjyXCszZTJIWyvCX5mQeTBTua2ymmG_Y8d4AcRHA==&uniplatform=NZKPT&language=CHS",
        "filename": "桂华_贺雪峰_2025_走向群众自觉行动的基层治理实践.pdf",
    },
    {
        "title": "资源下乡背景下的基层治理重塑与改进",
        "abstract_url": f"{VPN_BASE}/kcms2/article/abstract?v=lcJiu7QxtGNI2EudibMiw7s81NEcy_qevYzA36KZe-1h-PKrKSuj3QvwC269waknsi-qEIDai8hCd_OQg1Z6RC10A5XuOGdzxENNPPCN6ULtiAi1nWyAOq8yMPD7RMtLWZNyqoXM490Jv2N5YU401RZy7akwiSrMTfyxfTkvJtLBT95CEJ9iUA==&uniplatform=NZKPT&language=CHS",
        "filename": "贺雪峰_桂华_2025_资源下乡背景下的基层治理重塑.pdf",
    },
    {
        "title": "以村民小组为基础推进基层治理现代化",
        "abstract_url": f"{VPN_BASE}/kcms2/article/abstract?v=lcJiu7QxtGNcLtThXiNfDKVPAcrkXIUFC22gV8CzxKTkHn4GvwHGppEYWwWLBD-cKXKWZKfSrBopc2SPIf784hofn0pdQ9Q6hA7HBi90gbwTrmojJmFmAA839zOXI66p6x5d0EaoXA3e3B58AE5zITRLgU7RJi2pmhfA-Yxb1y238uWOgs_Xag==&uniplatform=NZKPT&language=CHS",
        "filename": "贺雪峰_2026_以村民小组为基础推进基层治理现代化.pdf",
    },
    {
        "title": "村级治理中的重治理与轻治理",
        "abstract_url": f"{VPN_BASE}/kcms2/article/abstract?v=lcJiu7QxtGMwsUdfNMLjFuTsOnm3gye-RhEd5ihKY_U7dhU3fkcV0ai3RZr0zekKug6rBF44dL67XEFVdFjg0We0OLZ5JYfsugTOjrceY9292ITL488TGk2mhyTA4xlSiqVO1LqJkTmtN2OQ4Hu5Z20kJ3Bxi1o5TuiNxFOxO2LpKcsf6RMEsw==&uniplatform=NZKPT&language=CHS",
        "filename": "贺雪峰_2025_村级治理中的重治理与轻治理.pdf",
    },
]

def main():
    print(f"📚 开始批量下载 {len(PAPERS)} 篇论文到 {SAVE_DIR}")
    print(f"📡 VPN Base: {VPN_BASE}")
    print()

    success = 0
    for i, paper in enumerate(PAPERS, 1):
        print(f"[{i}/{len(PAPERS)}] {paper['title'][:50]}...")

        # 检查是否已存在
        if (SAVE_DIR / paper['filename']).exists():
            print(f"  ⏭️ 已存在，跳过")
            success += 1
            continue

        pdf_url = get_pdf_url(paper['abstract_url'])
        if pdf_url:
            if download_pdf(pdf_url, paper['filename']):
                success += 1

        time.sleep(2)  # 礼貌间隔

    print(f"\n{'='*50}")
    print(f"✅ 完成: {success}/{len(PAPERS)} 篇下载成功")
    print(f"📁 保存位置: {SAVE_DIR}")


if __name__ == "__main__":
    main()
