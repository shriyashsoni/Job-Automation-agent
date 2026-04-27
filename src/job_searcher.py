import asyncio
from urllib.parse import quote_plus

class JobSearcher:
    def __init__(self, browser_manager):
        self.bm = browser_manager

    async def search_linkedin_jobs(self, query, location="Remote", limit=15, page=None):
        print(f"Searching for '{query}' jobs in '{location}' on LinkedIn...", flush=True)
        should_close = False
        if not page:
            page = await self.bm.start()
            should_close = True
        
        # Using the jobs search URL directly
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(query)}&location={quote_plus(location)}&f_TPR=r604800" # Last week
        try:
            await page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            # Scroll to load more jobs
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            job_links = []
            # Try multiple selectors for LinkedIn
            links = await page.query_selector_all("a.base-card__full-link, a.job-card-container__link, .base-search-card__title a")
            for link in links:
                url = await link.get_attribute("href")
                if url and ("jobs/view" in url or "jobs/search" not in url):
                    clean_url = url.split("?")[0]
                    if clean_url not in job_links:
                        job_links.append(clean_url)
                        if len(job_links) >= limit:
                            break
            
            print(f"Found {len(job_links)} jobs on LinkedIn.")
            return job_links
        except Exception as e:
            print(f"LinkedIn search failed: {e}")
            return []
        finally:
            if should_close:
                await self.bm.stop()

    async def search_web3_career(self, query, location="Remote", limit=15, page=None):
        print(f"Searching for '{query}' jobs on Web3.career...", flush=True)
        should_close = False
        if not page:
            page = await self.bm.start()
            should_close = True
        
        try:
            clean_query = quote_plus(query.lower())
            search_url = f"https://web3.career/?search={clean_query}"
            if location and location.lower() == "remote":
                search_url += "&location=Remote"
            
            await page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            job_links = []
            # More aggressive link searching
            links = await page.query_selector_all("a")
            for link in links:
                url = await link.get_attribute("href")
                if url and "/jobs/" in url and "web3.career" in url:
                    if not url.startswith("http"):
                        url = "https://web3.career" + url
                    url = url.split("?")[0]
                    if url not in job_links:
                        job_links.append(url)
                        if len(job_links) >= limit:
                            break
            
            print(f"Found {len(job_links)} jobs on Web3.career.")
            return job_links
        except Exception as e:
            print(f"Web3.career search failed: {e}")
            return []
        finally:
            if should_close:
                await self.bm.stop()

    async def search_cryptojobslist(self, query, location="Remote", limit=15, page=None):
        print(f"Searching for '{query}' jobs on CryptoJobsList...", flush=True)
        should_close = False
        if not page:
            page = await self.bm.start()
            should_close = True
        
        try:
            search_url = f"https://cryptojobslist.com/jobs?q={quote_plus(query)}&l={quote_plus(location)}"
            await page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            job_links = []
            links = await page.query_selector_all("a[href*='/jobs/']")
            for link in links:
                url = await link.get_attribute("href")
                if url:
                    if not url.startswith("http"):
                        url = "https://cryptojobslist.com" + url
                    url = url.split("?")[0]
                    if url not in job_links:
                        job_links.append(url)
                        if len(job_links) >= limit:
                            break
            
            print(f"Found {len(job_links)} jobs on CryptoJobsList.")
            return job_links
        except Exception as e:
            print(f"CryptoJobsList search failed: {e}")
            return []
        finally:
            if should_close:
                await self.bm.stop()

    async def search_remoteok(self, query, limit=15, page=None):
        try:
            search_url = f"https://remoteok.com/remote-jobs?q={quote_plus(query)}"
            await page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            job_links = []
            links = await page.query_selector_all("tr.job a.preventLink, tr.job a[href*='/remote-jobs/']")
            for link in links:
                url = await link.get_attribute("href")
                if url:
                    if not url.startswith("http"):
                        url = "https://remoteok.com" + url
                    url = url.split("?")[0]
                    if url not in job_links:
                        job_links.append(url)
                        if len(job_links) >= limit:
                            break
            
            print(f"Found {len(job_links)} jobs on RemoteOK.")
            return job_links
        except Exception as e:
            print(f"RemoteOK search failed: {e}")
            return []
        finally:
            if should_close:
                await self.bm.stop()

    async def search_workable(self, query, limit=15, page=None):
        print(f"Searching for '{query}' jobs on Workable...", flush=True)
        should_close = False
        if not page:
            page = await self.bm.start()
            should_close = True
            
        try:
            # Workable has a main job board
            search_url = f"https://www.workable.com/jobs?query={quote_plus(query)}"
            await page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            # Scroll to load more
            for _ in range(2):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
            job_links = []
            links = await page.query_selector_all("a[href*='workable.com/j/'], a[href*='apply.workable.com/']")
            for link in links:
                url = await link.get_attribute("href")
                if url:
                    if not url.startswith("http"):
                        url = "https://www.workable.com" + url
                    url = url.split("?")[0]
                    if url not in job_links:
                        job_links.append(url)
                        if len(job_links) >= limit:
                            break
            
            print(f"Found {len(job_links)} jobs on Workable.")
            return job_links
        except Exception as e:
            print(f"Workable search failed: {e}")
            return []
        finally:
            if should_close:
                await self.bm.stop()

    async def search_curated_companies(self, limit=15, page=None):
        print("Searching curated top blockchain company career pages...", flush=True)
        should_close = False
        if not page:
            page = await self.bm.start()
            should_close = True
            
        companies = [
            ("Binance", "https://www.binance.com/en/careers"),
            ("Aptos", "https://aptoslabs.com/careers"),
            ("Mysten Labs (Sui)", "https://mystenlabs.com/careers"),
            ("Solana", "https://solana.com/careers"),
            ("Polygon", "https://polygon.technology/careers"),
            ("Ava Labs", "https://www.avalabs.org/careers"),
            ("Offchain Labs", "https://offchainlabs.com/careers"),
            ("Optimism", "https://www.optimism.io/careers"),
            ("Chainlink", "https://chain.link/careers"),
            ("Coinbase", "https://www.coinbase.com/careers"),
            ("Circle", "https://www.circle.com/en/careers"),
            ("Ripple", "https://ripple.com/careers"),
            ("ConsenSys", "https://consensys.net/careers"),
            ("OpenSea", "https://opensea.io/careers"),
            ("Uniswap", "https://uniswap.org/careers"),
            ("Aave", "https://aave.com/careers"),
            ("Compound", "https://compound.finance/careers"),
            ("Lido", "https://lido.fi/careers"),
            ("MakerDAO", "https://makerdao.com/en/careers"),
            ("Arbitrum", "https://offchainlabs.com/careers"),
            ("Starknet", "https://starkware.co/careers/"),
            ("ZkSync", "https://zksync.io/careers"),
        ]
        
        job_links = []
        for name, url in companies:
            if len(job_links) >= limit:
                break
            print(f"Checking {name} careers: {url}", flush=True)
            try:
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(3) # Wait for redirects to settle
                
                # Broad scroll
                await page.evaluate("window.scrollTo(0, 1000)")
                await asyncio.sleep(1)
                
                # Look for Lever/Greenhouse/Workable links or internal job links
                links = await page.query_selector_all("a")
                for link in links:
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                        
                    is_direct_board = any(x in href for x in ["greenhouse.io", "lever.co", "workable.com", "ashbyhq.com", "bamboohr.com"])
                    is_job_path = any(x in href.lower() for x in ["/jobs/", "/open-positions/", "/career/", "/role/"])
                    
                    if is_direct_board or is_job_path:
                        if not href.startswith("http"):
                            base = "/".join(url.split("/")[:3])
                            href = base + (href if href.startswith("/") else "/" + href)
                        
                        if href not in job_links:
                            # Heuristic for job detail pages
                            if is_direct_board or (is_job_path and len(href.split("/")) > 4):
                                job_links.append(href)
                                if len(job_links) >= limit:
                                    break
            except Exception as e:
                print(f"Failed to check {name}: {e}")
                continue
                
        print(f"Found {len(job_links)} jobs from curated companies.")
        if should_close:
            await self.bm.stop()
        return job_links

    async def search_additional_sources(self, query, limit=15, page=None):
        print(f"Searching additional Web3 sources for '{query}'...", flush=True)
        should_close = False
        if not page:
            page = await self.bm.start()
            should_close = True
            
        additional_sources = [
            ("Crypto-Careers", f"https://crypto-careers.com/search?q={quote_plus(query)}"),
            ("CryptocurrencyJobs", f"https://cryptocurrencyjobs.co/?s={quote_plus(query)}"),
            ("BeInCrypto", f"https://beincrypto.com/jobs/?s={quote_plus(query)}"),
            ("JobStash", "https://jobstash.xyz/jobs"),
            ("Remote3", f"https://remote3.co/jobs?search={quote_plus(query)}"),
            ("Midnight", "https://midnight.network/careers"),
            ("Dragonfly", "https://jobs.dragonfly.xyz/jobs"),
            ("Block", "https://block.xyz/careers/jobs"),
            ("EthereumJobs", "https://ethereumjobboard.com/jobs"),
        ]
        
        job_links = []
        for name, url in additional_sources:
            if len(job_links) >= limit:
                break
            print(f"Checking {name}: {url}", flush=True)
            try:
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(4)
                
                # Broad link detection for specialized boards
                links = await page.query_selector_all("a")
                for link in links:
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                        
                    is_official = any(x in href for x in ["greenhouse.io", "lever.co", "workable.com", "ashbyhq.com", "bamboohr.com"])
                    is_job_path = any(x in href.lower() for x in ["/jobs/", "/open-positions/", "/career/"])
                    
                    if is_official or is_job_path:
                        if not href.startswith("http"):
                            base = "/".join(url.split("/")[:3])
                            href = base + (href if href.startswith("/") else "/" + href)
                        
                        if href not in job_links:
                            if is_official or (is_job_path and len(href.split("/")) > 4):
                                job_links.append(href)
                                if len(job_links) >= limit:
                                    break
            except Exception as e:
                print(f"Failed to check {name}: {e}")
                continue
                
        print(f"Found {len(job_links)} jobs from additional sources.")
        if should_close:
            await self.bm.stop()
        return job_links

    async def search_telegram(self, channel_url="https://t.me/web3hiring", limit=10, page=None):
        print(f"Checking Telegram channel: {channel_url}...", flush=True)
        should_close = False
        if not page:
            page = await self.bm.start()
            should_close = True
            
        job_links = []
        try:
            if "t.me/s/" not in channel_url:
                channel_url = channel_url.replace("t.me/", "t.me/s/")
                
            await page.goto(channel_url, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(4)
            
            links = await page.query_selector_all(".tgme_widget_message_text a")
            for link in links:
                href = await link.get_attribute("href")
                if href and any(x in href for x in ["greenhouse.io", "lever.co", "workable.com", "ashbyhq.com"]):
                    if href not in job_links:
                        job_links.append(href)
                        if len(job_links) >= limit:
                            break
        except Exception as e:
            print(f"Telegram search failed: {e}")
            
        print(f"Found {len(job_links)} jobs from Telegram.")
        if should_close:
            await self.bm.stop()
        return job_links
