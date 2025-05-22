import requests
from bs4 import BeautifulSoup
import json
import logging
from urllib.parse import urljoin, urlparse
from collections import deque
import time
from datetime import datetime

# 设置日志记录
logging.basicConfig(level=logging.INFO,
                   format="%(asctime)s %(levelname)s %(message)s")

class WebsiteCrawler:
    def __init__(self, start_url, output_file="web_data.json", delay=1):
        self.start_url = start_url
        self.output_file = output_file
        self.delay = delay  # 爬取延迟，避免对服务器压力过大
        self.domain = urlparse(start_url).netloc
        self.visited = set()
        self.queue = deque([start_url])
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def is_valid_url(self, url):
        """检查URL是否有效且属于同一域名"""
        try:
            parsed = urlparse(url)
            return parsed.netloc == self.domain and parsed.scheme in ['http', 'https']
        except ValueError:
            return False

    def extract_page_content(self, url, soup):
        """提取页面内容"""
        try:
            # 移除脚本和样式内容
            for script in soup(["script", "style"]):
                script.decompose()

            # 获取页面标题
            title = soup.title.string if soup.title else ""
            
            # 获取页面主要内容
            main_content = soup.get_text(separator='\n', strip=True)
            
            # 获取所有图片URL
            images = [img.get('src', '') for img in soup.find_all('img')]
            images = [urljoin(url, img) for img in images if img]

            # 获取页面描述
            meta_desc = ""
            meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_desc_tag:
                meta_desc = meta_desc_tag.get('content', '')

            return {
                "@type": "WebContent",
                "url": url,
                "title": title,
                "description": meta_desc,
                "content": main_content,
                "images": images,
                "crawled_at": datetime.now().isoformat()
            }
        except Exception as e:
            logging.error(f"Error extracting content from {url}: {str(e)}")
            return None

    def extract_links(self, soup, current_url):
        """提取页面中的所有链接"""
        links = []
        for link in soup.find_all('a'):
            href = link.get('href')
            if href:
                absolute_url = urljoin(current_url, href)
                if self.is_valid_url(absolute_url) and absolute_url not in self.visited:
                    links.append(absolute_url)
        return links

    def crawl(self):
        """开始爬取网站"""
        logging.info(f"Starting crawl from {self.start_url}")
        
        # 创建或清空输出文件
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write("")

        while self.queue:
            current_url = self.queue.popleft()
            
            if current_url in self.visited:
                continue
                
            self.visited.add(current_url)
            logging.info(f"Crawling: {current_url}")

            try:
                response = requests.get(current_url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 提取页面内容
                page_data = self.extract_page_content(current_url, soup)
                
                if page_data:
                    # 保存页面数据
                    with open(self.output_file, "a", encoding="utf-8") as f:
                        json.dump(page_data, f, ensure_ascii=False)
                        f.write("\n")
                
                # 提取新链接并添加到队列
                new_links = self.extract_links(soup, current_url)
                self.queue.extend(new_links)
                
                # 延迟，避免对服务器压力过大
                time.sleep(self.delay)
                
            except (requests.RequestException, IOError) as e:
                logging.error(f"Error processing {current_url}: {str(e)}")
                continue

        logging.info(f"Crawl completed. Processed {len(self.visited)} pages.")

def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description='网站内容提取工具')
    parser.add_argument('url', help='要爬取的网站URL')
    parser.add_argument('--output', default='web_data.json', help='输出文件名')
    parser.add_argument('--delay', type=float, default=1.0, help='爬取延迟(秒)')
    
    args = parser.parse_args()
    
    try:
        crawler = WebsiteCrawler(args.url, args.output, args.delay)
        crawler.crawl()
    except KeyboardInterrupt:
        logging.info("爬取被用户中断")
    except Exception as e:
        logging.error(f"爬取过程中发生错误: {str(e)}")

if __name__ == "__main__":
    main()