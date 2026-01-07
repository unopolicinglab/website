#!/usr/bin/env python3
"""
Media Mentions Parser for UNO Policing Lab
Parses markdown media mentions and generates JSON and RSS feeds
Enhanced to extract article titles from URLs
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse, unquote
import xml.etree.ElementTree as ET
from xml.dom import minidom

class MediaMention:
    """Represents a single media mention"""
    
    def __init__(self, title: str, url: str, source: str, date: str, 
                 summary: str = "", mention_type: str = "referenced",
                 topics: List[str] = None, featured: bool = False):
        self.title = title
        self.url = url
        self.source = source
        self.date = date
        self.summary = summary
        self.mention_type = mention_type
        self.topics = topics or []
        self.featured = featured
        self.relevance_confidence = "high"
        
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "date": self.date,
            "summary": self.summary,
            "mention_type": self.mention_type,
            "topics": self.topics,
            "featured": self.featured,
            "relevance_confidence": self.relevance_confidence,
            "date_discovered": self.date
        }


class MediaMentionsParser:
    """Parses markdown media mentions and generates outputs"""
    
    # Common topic mapping based on outlet and content
    OUTLET_TOPICS = {
        "USA Today": ["police", "national news", "policy"],
        "Denver Post": ["police", "regional", "Colorado"],
        "Milwaukee Journal Sentinel": ["police", "regional"],
        "KETV": ["police", "regional", "local", "Nebraska"],
        "New York Times": ["police", "national news", "use of force"],
        "Mother Jones": ["police", "civil liberties", "policy"],
        "Washington Post": ["police", "national news", "accountability"],
        "Wyoming Public Media": ["police", "regional", "Mountain West"],
        "Tampa Bay Times": ["police", "regional", "accountability"],
        "NPR": ["police", "national news", "research"],
        "Omaha World-Herald": ["police", "regional", "Nebraska", "local"],
        "NBC News": ["police", "national news", "use of force"],
        "Salt Lake Tribune": ["police", "regional", "Mountain West"],
        "Fox News": ["police", "national news", "accountability"],
        "Reuters": ["police", "national news", "research"],
        "Houston Chronicle": ["police", "regional", "crime"],
        "The Reader": ["police", "regional", "Nebraska", "local"],
        "Boise State Public Radio": ["police", "regional", "Mountain West"],
        "Cronkite News": ["police", "regional", "Arizona"],
        "Baltimore Sun": ["police", "regional", "accountability"],
        "Healthline": ["health", "police", "COVID"],
        "Dallas Morning News": ["police", "regional", "protests"],
        "ABC News": ["police", "national news", "bias"],
        "Wall Street Journal": ["police", "national news", "reform"],
        "LA Times": ["police", "regional", "California", "use of force"],
        "Nature": ["research", "police", "science"],
        "Lincoln Journal Star": ["police", "regional", "Nebraska", "local"],
        "Newsy": ["police", "national news"],
        "Die Welt": ["police", "international"],
        "Texas Tribune": ["police", "regional", "policy"],
        "The Trace": ["police", "guns", "data"],
        "Arizona Republic": ["police", "regional", "use of force"],
        "Santa Fe Reporter": ["police", "regional"],
        "Phoenix New Times": ["police", "regional", "Arizona"],
        "CityLab": ["police", "policy", "equity"],
        "Indianapolis Star": ["police", "regional", "shooting"],
        "Minneapolis Star Tribune": ["police", "regional", "Minnesota"],
        "Wichita Eagle": ["police", "regional", "Kansas"],
        "Topeka Capital Journal": ["police", "regional", "Kansas"],
        "WIRED": ["police", "technology", "data"],
        "BuzzFeed News": ["police", "bias", "race"],
        "The Globe and Mail": ["police", "international"],
        "New York Magazine": ["police", "research"],
        "American Psychological Association": ["research", "police"],
    }
    
    def __init__(self):
        self.mentions: List[MediaMention] = []
    
    @staticmethod
    def extract_title_from_url(url: str) -> Optional[str]:
        """Extract a readable title from URL slug"""
        try:
            # Parse URL
            parsed = urlparse(url)
            path = parsed.path
            
            # Get the last meaningful part of the path
            parts = [p for p in path.split('/') if p]
            if not parts:
                return None
            
            # Get last part (usually the slug)
            slug = parts[-1]
            
            # Clean up common patterns
            slug = slug.replace('.html', '').replace('.php', '')
            
            # Split on hyphens and capitalize
            words = slug.split('-')
            # Filter out common short words
            title_words = []
            for word in words:
                if word.lower() not in ['the', 'a', 'an', 'and', 'or', 'in', 'on', 'at', 'to', 'for']:
                    title_words.append(word)
                elif len(title_words) == 0:  # Keep first article
                    title_words.append(word)
            
            # Remove numbers and common fragments
            title_words = [w for w in title_words if not w.isdigit() and len(w) > 2]
            
            if not title_words:
                return None
            
            title = ' '.join(title_words).title()
            return title if len(title) > 5 else None
        except:
            return None
    
    def parse_markdown(self, markdown_text: str) -> None:
        """Parse markdown format: * YYYY: [Outlet](url), [Outlet](url), ..."""
        
        lines = markdown_text.strip().split('\n')
        
        for line in lines:
            # Skip header and empty lines
            if line.startswith('#') or not line.strip() or line.startswith('##'):
                continue
            
            # Parse year line: * YYYY: [Outlet](url), [Outlet](url), ...
            year_match = re.match(r'\*\s*(\d{4}):\s*(.*)', line)
            if not year_match:
                continue
            
            year = year_match.group(1)
            links_text = year_match.group(2)
            
            # Extract all [text](url) pairs
            link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
            links = re.findall(link_pattern, links_text)
            
            for outlet, url in links:
                # Extract source name (remove "The" if present)
                source = outlet.replace('The ', '').strip()
                
                # Generate date (use first day of year for simplicity)
                date = f"{year}-01-01"
                
                # Get topics from mapping, default to generic topics
                topics = self.OUTLET_TOPICS.get(source, ["police", "news"])
                
                # Extract title from URL or use a default
                article_title = self.extract_title_from_url(url)
                if not article_title:
                    article_title = f"{source} ({year})"
                
                # Create mention with extracted title as summary
                mention = MediaMention(
                    title=f"{source} - {year}",
                    url=url,
                    source=source,
                    date=date,
                    summary=article_title,  # Use extracted title as summary
                    mention_type="referenced",
                    topics=topics,
                    featured=False
                )
                
                self.mentions.append(mention)
    
    def sort_by_date(self) -> None:
        """Sort mentions by date (newest first)"""
        self.mentions.sort(
            key=lambda x: datetime.strptime(x.date, "%Y-%m-%d"),
            reverse=True
        )
    
    def generate_json(self) -> str:
        """Generate JSON output"""
        data = {
            "metadata": {
                "total_mentions": len(self.mentions),
                "last_updated": datetime.now().isoformat(),
                "sources": list(set(m.source for m in self.mentions)),
                "date_range": {
                    "earliest": min(m.date for m in self.mentions) if self.mentions else None,
                    "latest": max(m.date for m in self.mentions) if self.mentions else None
                }
            },
            "stories": [m.to_dict() for m in self.mentions]
        }
        return json.dumps(data, indent=2)
    
    def generate_rss(self, title: str = "UNO Policing Lab Media Mentions",
                     link: str = "https://www.viprlab.org/media/",
                     description: str = "Media coverage featuring UNO Policing Lab research") -> str:
        """Generate RSS feed"""
        
        rss = ET.Element('rss')
        rss.set('version', '2.0')
        rss.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
        
        channel = ET.SubElement(rss, 'channel')
        
        ET.SubElement(channel, 'title').text = title
        ET.SubElement(channel, 'link').text = link
        ET.SubElement(channel, 'description').text = description
        ET.SubElement(channel, 'language').text = 'en-us'
        ET.SubElement(channel, 'lastBuildDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
        
        # Add items (limit to 50 most recent)
        for mention in self.mentions[:50]:
            item = ET.SubElement(channel, 'item')
            
            ET.SubElement(item, 'title').text = mention.title
            ET.SubElement(item, 'link').text = mention.url
            ET.SubElement(item, 'source').text = mention.source
            
            # Description with summary
            description_text = f"{mention.summary}\n\nSource: {mention.source}\nType: {mention.mention_type.title()}"
            if mention.topics:
                description_text += f"\nTopics: {', '.join(mention.topics)}"
            ET.SubElement(item, 'description').text = description_text
            
            # Pub date
            date_obj = datetime.strptime(mention.date, "%Y-%m-%d")
            ET.SubElement(item, 'pubDate').text = date_obj.strftime('%a, %d %b %Y 12:00:00 +0000')
            
            # GUID
            ET.SubElement(item, 'guid').text = mention.url
            
            # Categories (topics)
            for topic in mention.topics:
                cat = ET.SubElement(item, 'category')
                cat.text = topic
        
        # Pretty print XML
        xml_str = minidom.parseString(ET.tostring(rss)).toprettyxml(indent="  ")
        # Remove empty lines
        xml_str = '\n'.join([line for line in xml_str.split('\n') if line.strip()])
        # Remove XML declaration line if duplicate
        lines = xml_str.split('\n')
        if lines[0].startswith('<?xml') and len(lines) > 1 and lines[1].startswith('<?xml'):
            xml_str = '\n'.join(lines[1:])
        
        return xml_str


def main():
    """Main entry point"""
    
    # Your media mentions markdown
    markdown = """## Selected Media Contributions

* 2025: [USA Today](https://www.usatoday.com/story/news/politics/2025/11/16/michael-pickett-birmingham-alabama-police-chief/87114615007/), [The Denver Post](https://www.denverpost.com/2025/04/20/colorado-police-chases-deaths-injuries-westminster-aurora/), [Milwaukee Journal Sentinel](https://www.jsonline.com/story/news/investigations/2025/08/20/milwaukee-police-officer-was-on-brady-list-twice-before-he-was-fired/85364335007/), [KETV](https://www.ketv.com/article/ketv-investigates-exclusive-omaha-police-department-shares-new-look-at-overall-crime/64786856), [New York Times](https://www.nytimes.com/2025/05/24/us/police-killings-george-floyd.html), [Mother Jones](https://www.motherjones.com/politics/2025/06/ice-immigration-agents-masks-masking-concealing-faces-legal/)
* 2024: [The Washington Post](https://www.washingtonpost.com/dc-md-va/2024/10/09/dc-audits-mpd-extremism/), [USA Today](https://www.usatoday.com/story/news/nation/2024/01/11/police-officer-killings-2023/72152566007/), [Wyoming Public Media](https://www.wyomingpublicmedia.org/2024-08-05/violent-crime-is-down-across-the-country-but-rates-are-mixed-in-the-mountain-west), [Tampa Bay Times](https://www.tampabay.com/news/crime/2024/08/15/hillsborough-state-attorney-election-race/)
* 2023: [NPR](https://www.npr.org/2023/10/20/1207276234/fbi-crime-report-takeaways), [The Washington Post](https://www.unionleader.com/news/safety/fatal-police-shootings-are-still-going-up-and-nobody-knowswhy/article_121cc480-7ac6-57a6-8b84-5ef735ecfe6b.html), [Omaha World-Herald](https://omaha.com/news/local/staffing-woes-continue-to-plague-omaha-police-department/article_19b630de-bea5-11ed-b07c-9b7f82541a13.html)
* 2022: [NBC News](https://www.nbcnews.com/news/us-news/gonna-lose-gun-idaho-deputy-said-minutes-fatally-shooting-man-mental-h-rcna33601), [Salt Lake Tribune](https://www.sltrib.com/news/2022/01/21/utah-broke-record-most/), [USA Today](https://www.usatoday.com/story/news/nation/2022/01/29/police-attacked-4-us-cities-within-week-amid-violent-crime-spike/9248049002/?gnt-cfr=1), [Fox News](https://www.foxnews.com/politics/washington-d-c-police-withhold-key-details-about-homicide-unit-amid-murder-surge), [Denver Post](https://www.denverpost.com/2022/07/20/denver-police-shooting-lodo-injuries/)
* 2021: [Reuters](https://www.reuters.com/legal/government/after-floyds-killing-minneapolis-police-retreated-data-shows-2021-09-13/), [Salt Lake Tribune](https://www.sltrib.com/news/2021/09/20/new-data-utah-police/), [The New York Times](https://www.nytimes.com/2021/07/23/upshot/murder-crime-solving.html), [The Washington Post](https://www.washingtonpost.com/investigations/interactive/2021/police-shootings-since-2015/), [Houston Chronicle](https://www.houstonchronicle.com/news/article/Domestic-violence-calls-for-help-increased-during-16114201.php), [Omaha World-Herald](https://omaha.com/news/local/crime-and-courts/violent-crime-rose-in-2020-while-property-crime-dropped-a-look-at-omaha-during-the/article_97ab10ee-963a-11eb-88d2-631cd75b0b83.html), [USA Today](https://www.usatoday.com/story/news/factcheck/2021/04/28/fact-check-posts-days-without-police-killings-2021-true/7332866002/), [The Reader](https://thereader.com/news/its-evil-its-ruthless-five-months-after-omaha-police-shooting-questions-remain), [Boise State Public Radio](https://www.boisestatepublicradio.org/news/2021-01-25/mountain-west-has-the-highest-rate-of-people-killed-by-police-in-the-nation)
* 2020: [Cronkite News](https://cronkitenews.azpbs.org/2020/01/03/phoenix-police-shootings-dropped-in-2019-after-sharp-spike-in-2018/), [The Baltimore Sun](https://www.baltimoresun.com/maryland/baltimore-city/bs-md-ci-police-overtime-20200207-z43l2amv3vf3lb4rtgsvfeye6i-story.html), [Healthline](https://www.healthline.com/health-news/what-do-we-do-if-our-police-firefighters-and-paramedics-all-get-sick-with-covid-19), [Dallas Morning News](https://www.dallasnews.com/news/crime/2020/06/02/dallas-police-chief-renee-hall-says-demonstrators-broke-law-when-they-walked-onto-margaret-hunt-hill-bridge/), [ABC News](https://abcnews.go.com/US/latest-research-tells-us-racial-bias-policing/story?id=70994421), [Wall Street Journal](https://www.wsj.com/articles/a-minneapolis-police-chief-promised-change-george-floyds-death-shows-hurdles-11590971860), [The Reader](https://thereader.com/news/black-drivers-more-likely-to-receive-harsh-outcomes-in-traffic-stops), [The Denver Post](https://www.denverpost.com/2020/06/13/colorado-police-reform-bill-passes-legislature/), [Crusoé](https://crusoe.com.br/edicoes/111/americanos-contra-os-tiras/), [LA Times](https://www.latimes.com/opinion/story/2020-06-17/police-shootings-data), [Nature](https://www.nature.com/articles/d41586-020-01846-z), [Omaha World Herald](https://www.omaha.com/news/local/what-went-wrong-at-72nd-and-dodge-the-anatomy-of-omahas-may-29-street-conflict/article_d943cc78-52a3-5f67-8f43-ac642922e5bc.html), [Lincoln Journal Star](https://journalstar.com/news/local/crime-and-courts/protesters-describe-being-shot-gassed-during-black-lives-matter-rallies/article_dadfbf6c-1649-54ad-8e43-67e48e174dcb.html), [Newsy](https://www.newsy.com/stories/police-can-ignore-fbi-request-for-use-of-force-data/), [Die Welt](https://www.welt.de/wissenschaft/article210167603/Polizeigewalt-in-USA-Neue-Strategien-zur-Deeskalation.html), [Texas Tribune](https://www.texastribune.org/2020/07/02/texas-police-george-floyd/), [The Trace](https://www.thetrace.org/2020/07/guns-policing-how-many-deaths-data-statistics/), [Arizona Republic](https://www.azcentral.com/restricted/?return=https%3A%2F%2Fwww.azcentral.com%2Fin-depth%2Fnews%2Flocal%2Fphoenix%2F2020%2F08%2F10%2Fphoenix-police-use-force-data-black-latino-native-impact%2F5407299002%2F), [Tampa Bay Times](https://www.tampabay.com/news/crime/2020/10/13/has-crime-gone-up-or-down-in-tampa-state-attorney-candidates-differ/?utm_source=twitter&utm_content=%40tbtnewspaper&utm_campaign=SocialFlow&utm_medium=social), [Santa Fe Reporter](https://www.sfreporter.com/news/2020/10/22/us-versus-them/)
* 2019: [ABC News](https://abcnews.go.com/Health/fatal-police-shootings-race-officer-predictive-civilians-race/story?id=64563567), [The Washington Post](https://www.washingtonpost.com/investigations/four-years-in-a-row-police-nationwide-fatally-shoot-nearly-1000-people/2019/02/07/0cb3b098-020f-11e9-9122-82e98f91ee6f_story.html?noredirect=on&utm_term=.8beeba6c1f0b), [Phoenix New Times](https://www.phoenixnewtimes.com/news/report-no-single-answer-for-2018-spike-in-phoenix-police-shootings-11273431), [CityLab](https://www.citylab.com/equity/2019/08/police-officer-shootings-gun-violence-racial-bias-crime-data/595528/), [Nature](https://www.nature.com/articles/d41586-019-02601-9), [Indianapolis Star](https://www.indystar.com/story/news/crime/2019/09/18/how-indianapolis-reduced-fatal-police-shootings-compared-new-york-chicago/1943601001/)
* 2018: [The Washington Post](https://www.washingtonpost.com/investigations/fatal-police-shootings-of-unarmed-people-have-significantly-declined-experts-say/2018/05/03/d5eab374-4349-11e8-8569-26fda6b404c7_story.html?noredirect=on&utm_term=.d2800bfb4d4f), [The Wall Street Journal](https://www.wsj.com/articles/federal-count-of-deadly-police-shootings-is-slow-to-get-going-1522494001), [New York Times](https://www.nytimes.com/2018/03/30/us/stephon-clark-independent-autopsy.html), [The Huffington Post](https://www.huffingtonpost.com/entry/gun-deaths-car-deaths_us_5b6b3337e4b0530743c676c8), [Minneapolis Star Tribune](http://www.startribune.com/after-charges-in-damond-killing-racial-dynamic-remains-a-focal-point/477827553/), [Wichita Eagle](http://www.kansas.com/news/local/article194338784.html), [Topeka Capital Journal](http://cjonline.com/news/local/crime-courts/2018-01-04/criminal-justice-professor-topeka-police-officers-had-authority)
* 2017: [USA Today](https://www.usatoday.com/story/news/2017/12/28/number-officers-killed-2017-hits-nearly-50-year-low/984477001/), [WIRED](https://www.wired.com/2017/02/us-needs-real-data-confront-bias-police-shootings), [CityLab](http://www.citylab.com/crime/2017/02/is-reverse-racism-among-police-real/513503/), [Omaha World-Herald](http://www.omaha.com/news/nebraska/video-shows-use-of-force-after-sioux-county-chase-raises/article_50d3bc92-e2de-5fd8-a4ab-a9a6966a1d63.html), [The Lincoln Journal Star](http://journalstar.com/news/local/911/a-persisting-problem-lpd-probes-into-the-racial-disparities-in/article_30cc2fce-1e97-5362-9777-63ca24ed029a.html)
* 2016: [Buzzfeed News](https://www.buzzfeed.com/peteraldhous/race-and-police-force?utm_term=.to1jrQ82x#.ke9mzqjgZ), [The Washington Post](https://www.washingtonpost.com/national/study-finds-police-fatally-shoot-unarmed-black-men-at-disproportionate-rates/2016/04/06/e494563e-fa74-11e5-80e4-c381214de1a3_story.html?tid=sm_tw), [The Denver Post](http://www.denverpost.com/2016/07/27/commerce-city-asks-feds-for-help-with-police/), [The Globe and Mail](http://www.theglobeandmail.com/news/world/after-a-violent-week-two-measures-to-make-policing-better/article30873038/?cmpid=rss1&click=sf_globe)
* 2015: [The Huffington Post](http://www.huffingtonpost.com/entry/ferguson-effect-police-study_us_5630d33ee4b0c66bae5a41ab), [New York Magazine](http://nymag.com/scienceofus/2015/10/research-rebuts-the-idea-of-a-ferguson-effect.html), [American Psychological Association](http://www.apa.org/news/press/releases/2015/10/police-motivation.aspx)
"""
    
    # Parse
    parser = MediaMentionsParser()
    parser.parse_markdown(markdown)
    parser.sort_by_date()
    
    # Generate outputs
    json_output = parser.generate_json()
    rss_output = parser.generate_rss()
    
    print("Generated JSON:")
    print(json_output[:500] + "...")
    print("\n" + "="*80 + "\n")
    print("Generated RSS (first 500 chars):")
    print(rss_output[:500] + "...")
    
    # Write to files
    with open('media-mentions.json', 'w') as f:
        f.write(json_output)
    print(f"\nJSON written to media-mentions.json")
    
    with open('media-mentions.xml', 'w') as f:
        f.write(rss_output)
    print(f"RSS written to media-mentions.xml")


if __name__ == '__main__':
    main()
