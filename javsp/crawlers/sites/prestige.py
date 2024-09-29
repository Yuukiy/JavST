"""从蚊香社-prestige抓取数据"""
import re
import logging



from javsp.crawlers.exceptions import MovieNotFoundError, SiteBlocked
from javsp.datatype import MovieInfo
from javsp.network.utils import resolve_site_fallback
from javsp.network.client import get_session
from javsp.crawlers.interface import Crawler
from javsp.config import CrawlerID
from lxml import html


logger = logging.getLogger(__name__)


class PrestigeCrawler(Crawler):
    id = CrawlerID.prestige

    @classmethod
    async def create(cls): 
        self = cls()
        url = await resolve_site_fallback(self.id, 'https://www.prestige-av.com')
        self.base_url = str(url)
        self.client = get_session(url)
        # prestige要求访问者携带已通过R18认证的cookies才能够获得完整数据，否则会被重定向到认证页面
        # （其他多数网站的R18认证只是在网页上遮了一层，完整数据已经传回，不影响爬虫爬取）
        self.client.cookie_jar.update_cookies({'__age_auth__': 'true'})
        return self

    async def crawl_and_fill(self, movie: MovieInfo) -> None:
        """从网页抓取并解析指定番号的数据
        Args:
            movie (MovieInfo): 要解析的影片信息，解析后的信息直接更新到此变量内
        """
        url = f'{self.base_url}/goods/goods_detail.php?sku={movie.dvdid}'
        resp = await self.client.get(url)
        if resp.status == 500:
            # 500错误表明prestige没有这部影片的数据，不是网络问题，因此不再重试
            raise MovieNotFoundError(__name__, movie.dvdid)
        elif resp.status == 403:
            raise SiteBlocked('prestige不允许从当前IP所在地区访问，请尝试更换为日本地区代理')
        resp.raise_for_status()
        tree = html.fromstring(await resp.text())
        container_tags = tree.xpath("//section[@class='px-4 mb-4 md:px-8 md:mb-16']")
        if not container_tags:
            raise MovieNotFoundError(__name__, movie.dvdid)

        container = container_tags[0]
        title = container.xpath("h1/span")[0].tail.strip()
        cover = container.xpath("//div[@class='c-ratio-image mr-8']/picture/source/img/@src")[0]
        cover = cover.split('?')[0]
        actress = container.xpath("//p[text()='出演者：']/following-sibling::div/p/a/text()")
        # 移除女优名中的空格，使女优名与其他网站保持一致
        actress = [i.strip().replace(' ', '') for i in actress]
        duration_str = container.xpath("//p[text()='収録時間：']")[0].getnext().text_content()
        match = re.search(r'\d+', duration_str)
        if match:
            movie.duration = match.group(0)
        date_url = container.xpath("//p[text()='発売日：']/following-sibling::div/a/@href")[0]
        publish_date = date_url.split('?date=')[-1]
        producer = container.xpath("//p[text()='メーカー：']/following-sibling::div/a/text()")[0].strip()
        dvdid = container.xpath("//p[text()='品番：']/following-sibling::div/p/text()")[0]
        genre_tags = container.xpath("//p[text()='ジャンル：']/following-sibling::div/a")
        genre = [tag.text.strip() for tag in genre_tags]
        serial = container.xpath("//p[text()='レーベル：']/following-sibling::div/a/text()")[0].strip()
        plot = container.xpath("//h2[text()='商品紹介']/following-sibling::p")[0].text.strip()
        preview_pics = container.xpath("//h2[text()='サンプル画像']/following-sibling::div/div/picture/source/img/@src")
        preview_pics = [i.split('?')[0] for i in preview_pics]

        # prestige改版后已经无法获取高清封面，此前已经获取的高清封面地址也已失效
        movie.url = url
        movie.dvdid = dvdid
        movie.title = title
        movie.cover = cover
        movie.actress = actress
        movie.publish_date = publish_date
        movie.producer = producer
        movie.genre = genre
        movie.serial = serial
        movie.plot = plot
        movie.preview_pics = preview_pics
        movie.uncensored = False    # prestige服务器在日本且面向日本国内公开发售，不会包含无码片



if __name__ == "__main__":

    async def test_main():
        crawler = await PrestigeCrawler.create()
        movie = MovieInfo('ABP-647')
        try:
          await crawler.crawl_and_fill(movie)
          print(movie)
        except Exception as e:
          print(repr(e))

    import asyncio
    asyncio.run(test_main())
