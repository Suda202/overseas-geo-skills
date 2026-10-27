# 社区与评价站：每个站用什么通道抓

收买家原话（评价、社区）时，先在这里查目标站走哪个通道，再派活。站点该不该收由 [signal-sources.md](signal-sources.md) 的行业表、市场表决定；本文件只回答「能不能抓、怎么抓」。表里没有的站，先按文末「怎么测一个新站」测过再派。实测日期 2026-10-27，测试记录在项目 `references/community-scrape-probe/`。

## 先查这几条

1. **评价平台优先走 DataForSEO**：Trustpilot、Google Play、App Store、Google Shopping、Google 地图都用 `shared/scripts/collect_reviews.py`（见 signal-sources.md）。
2. **其余站按通道从便宜往贵试**：`net.py fetch` 直连（免费）→ `net.py render` 无头 Chrome（免费）→ Scrapeless 不带 JS（`net.py fetch --proxy`，付费，每页 1 次）。不需要登录的页面不进 Suda 已登录的浏览器。
3. **Scrapeless 开 JS 渲染反而更差**：Reddit 弹人机验证，Facebook 报 `Navigating frame was detached`，X 报隧道连接失败。先用不带 JS 的。
4. **列表页能读不等于帖子能读**：下表多数站只测了版块页或列表页，真要收原话先拿一个帖子页再测。Pantip 静态 HTML 里的评论是模板占位符，必须走无头 Chrome。
5. **本机连不上的站只能走代理**：Facebook、X、Instagram、Threads、HardwareZone 直连都超时（本机没有系统代理）。
6. **找不到入口就先搜帖子**：Facebook 群首页翻不了页，用 `net.py search 'site:域名 关键词'` 先拿帖子固定链接，再逐帖取。

## 通用平台

| 站点 | 通道 | 能拿到什么 | 备注 |
|---|---|---|---|
| Reddit | `net.py reddit <版块/帖子 URL 或搜索词> [--sub 版块]`（RSS 直连，免费） | 版块最新帖、全站搜索、版内搜索、单帖加评论（实测 1 帖 + 46 条评论） | 未登录约每分钟 1 次，脚本按 `x-ratelimit-reset` 自动等待，不要并发；评论是扁平列表，没有楼层和点赞数。`.json`、old.reddit、无头 Chrome、Scrapeless、PullPush、Wayback 都不通 |
| Facebook 公开群 | `net.py fetch <帖子URL> --country SG --proxy --raw` | 帖子正文和大部分评论（8 条拿到 6 条） | 直连返回 400 登录页，必须加 `--proxy`。正文在内嵌 JSON 的 `message.text`，评论在 `body.text`，要去重。群首页只显示 2 帖、品牌主页 1 帖，翻不了页。不经过 Suda 的账号 |
| Google 地图评价 | `collect_reviews.py google-maps "<店名 分店 城市>" --country sg --lang en --match <品牌>`，或给 `place_id:<ID>` | 评价原文、星级、日期、单条评价链接；每 10 条计一次费（20 条 0.0015 美元） | 搜索词可能落到别的分店，脚本打印匹配到的商家名，`--match` 不符就记失败（这一次照样计费）；`--sort lowest` 先取差评找决策摩擦；只打星没写字的评价不收（新加坡一家店 20 条里有 8 条）；外语评价取原文不取机翻。Scrapeless 的地图采集器已下线（15002），无头 Chrome 只看到受限版页面，都不能用 |
| Trustpilot、Google Play、App Store | `collect_reviews.py` | 评价正文 | 无头 Chrome 也能读 Trustpilot；App Store 另有苹果公开 RSS（`itunes.apple.com/<区>/rss/customerreviews/page=1/id=<id>/sortby=mostrecent/json`，每页 50 条），Ybrand 美区 50 条、泰区和新加坡区 0 条，原因未确认 |
| YouTube | 直连 | 视频页、搜索页 | 评论正文没测 |
| TikTok | 直连 | 只有页面外壳 | 正文没拿到 |
| Threads | 有通道拿到主页 | 简介、粉丝数 | 帖子和回复没测 |
| LinkedIn 公开内容页 | 直连 | 页面可读 | — |
| Instagram、Quora、X | 不通 | — | Quora 被 Cloudflare 拦，三个通道都试过 |

## 按行业的评价站（对应 signal-sources.md「按行业收评价和社区」）

| 行业 | 直连 | 无头 Chrome | 只有 Scrapeless | 不通 |
|---|---|---|---|---|
| B2B 软件 | LinkedIn 公开页 | TrustRadius | — | G2、Capterra（Cloudflare）、Gartner Peer Insights |
| B2B 服务与代理 | Sortlist | — | Clutch、DesignRush | — |
| 工业品 | Alibaba | Global Sources | Made-in-China | ThomasNet |
| 医疗器械 | FDA MAUDE、COPD360social | — | — | — |
| 消费电子 | Amazon 商品页（.sg/.co.jp） | RTINGS | Best Buy、Wirecutter | Amazon 评价列表页（要登录；改用 `collect_reviews.py google-shopping`） |
| 美妆保健 | iHerb | — | — | Sephora 新加坡站 |
| 内容与流媒体 | MyDramaList 单篇评论 | — | — | — |
| 本地生活 | — | — | — | TripAdvisor、Yelp |

## 按市场的本地社区（对应 signal-sources.md「按目标市场换成当地平台」）

| 市场 | 直连 | 无头 Chrome | 只有 Scrapeless | 不通 |
|---|---|---|---|---|
| 新加坡 | RenoTalk、Qanvast | — | HardwareZone（版块和帖子页都能读）、Carousell | KiasuParents（403）、Seedly（只有前端外壳）、Shopee、Lazada |
| 马来西亚 | Lowyat（版块和帖子页都能读） | — | 佳礼 Cari | — |
| 泰国 | Wongnai、Jeban、Pantip 版块页 | Pantip 帖子页（实测 118 层评论全拿到） | Dek-D | — |
| 韩国 | Naver 搜索（블로그/VIEW）、지식iN、Clien、DCinside、Danawa、코인판 | — | 뽐뿌、FMKorea | 더쿠、쿠팡 |
| 台湾 | PTT 版块列表 | Mobile01、momo 购物网 | — | Dcard（Cloudflare） |
| 香港 | 香港討論區、OpenRice | LIHKG | — | — |
| 日本 | Amazon JP、价格.com 列表页 | — | — | — |

Naver Cafe 列表框架直连能读，帖子正文多数要先加入 Cafe，没测。韩国老站是 EUC-KR 编码，按 UTF-8 解码会乱码（Naver Cafe、뽐뿌）。

## 怎么测一个新站

1. 拿一个真实的帖子或评价页 URL，用 `net.py search 'site:域名 关键词'` 搜出来，不要凭印象拼：价格.com、MyDramaList、App Store 第一轮都因为 URL 是猜的被误判成不通。
2. 按第 2 条的顺序试三个通道。
3. 判断「能读」看正文：里面要有那条帖子或评价原文，而且不是验证页、登录页、404 页。只看 HTTP 200 或关键词会误判：ThomasNet 的 404 曾被判成能读，PTT、Lowyat、DCinside、Danawa、Coinpan 曾被判成不通，直连复核都能读。
4. 测完把结果补进上面的表，写明日期。
