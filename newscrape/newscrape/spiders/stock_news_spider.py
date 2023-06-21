import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from urllib.parse import urljoin
import re 
class VnExpressSpider(scrapy.Spider):
    name = 'vnexpress'
    allowed_domains = ['vnexpress.net']
    start_urls = [
        "https://vnexpress.net/kinh-doanh",
        "https://vnexpress.net/the-gioi"
    ]

    def parse(self, response):
        # get news page
        for new in response.css("article div.thumb-art a"):
            new_url = new.attrib['href']
            # Get image from the front page, then pass to cb_kwargs to callback function
            image = new.css("picture img.lazy::attr(data-src)").get()
            request = scrapy.Request(url=new_url, callback=self.parse_new_page, cb_kwargs={'image':image})
            request.cb_kwargs['image'] = image
            yield request

        # get next page
        next_page = response.css("div.button-page a.next-page").attrib['href']
        if next_page:
            url = urljoin('https://vnexpress.net', next_page)
            self.logger.info('Parse function called on %s', response.url)
            yield scrapy.Request(url=url, callback=self.parse)
        
    def parse_new_page(self, response, image):
        title = response.css("p.description::text").get()
        content = " ".join(response.css("article.fck_detail p.Normal::text").getall())
        author = response.css("article.fck_detail p.Normal")[-1].css("p.Normal strong::text").get()
        date = response.css("span.date::text").get()
        link = response.url
        yield {
            'title':title,
            'content':content,
            'link':link,
            'author':author,
            'date':date,
            'image':image
        }

class VnEconomySpider(scrapy.Spider):
    name = 'vneconomy'
    allowed_domains = ['vneconomy.vn']
    start_urls = [
        "https://vneconomy.vn/chung-khoan.htm",
    ]

    def parse(self, response):
        # get new pages
        for new in response.css("figure.story__thumb a"):
            new_url = 'https://vneconomy.vn' + new.attrib['href']
            yield scrapy.Request(url=new_url, callback=self.parse_new_page)

        # get next page 
        domain_name = re.sub("\d+", '', response.css("li.active a").attrib['href'])
        num_page = str(int(re.sub("\D", '', response.css("li.active a").attrib['href'])) + 1)
        next_page = domain_name + num_page   
        if next_page:
            url_ = urljoin('https://vneconomy.vn', next_page)
            self.logger.info('Parse function called on %s', response.url)
            yield scrapy.Request(url=url_, callback=self.parse)

    def parse_new_page(self, response):
        heading_1 = response.css("h1.detail__title::text").get()
        heading_2 = response.css("h2.detail__summary::text").get()
        title = str(heading_1) + " " + str(heading_2)
        author = response.css("div.detail__author strong::text").get()
        date = response.css("div.detail__meta::text").get()
        content = " ".join(response.css("div.detail__content p::text").extract())
        link = response.url
        yield {
            'title':title,
            'content':content,
            'link':link,
            'author':author,
            'date':date
        }
