# Product: Web Crawler System

> Исторический backlog развития распределённого краулера. Это план, а не перечень
> завершённых функций. Реализованный объём первой части ДЗ описан в [README.md](README.md).

## User Stories

### US-1: URL Discovery and Crawling
**As a** data analyst
**I want** to submit seed URLs and have them automatically crawled
**So that** I can collect web data at scale

**Acceptance Criteria:**
- System accepts batch upload of seed URLs
- URLs are distributed across crawler nodes using consistent hashing
- Respects robots.txt and crawl-delay directives
- Deduplicates URLs before crawling
- Stores raw HTML in S3 with content hash


---

## Sprint Backlog (1 week)

### Sprint Goal
Implement core crawler infrastructure with URL management and S3 storage

### Tasks

#### US-1: URL Discovery and Crawling

**T-1.1** Setup DynamoDB table with GSI on content_hash
**Estimate:** 2h (реально 1 день - разберешься с IAM permissions, регионами, CloudFormation)

**T-1.2** Implement consistent hashing for URL distribution
**Estimate:** 4h (реально 2-3 дня - edge cases, тестирование балансировки, отладка)

**T-1.3** Build robots.txt parser and local cache
**Estimate:** 3h (реально 1-2 дня - парсинг всех директив, TTL, кеш инвалидация, crawl-delay)

**T-1.4** Create downloader service with HTTP client
**Estimate:** 4h (реально 3-5 дней - таймауты, ретраи, rate limiting, proxy rotation, anti-bot bypass)

**T-1.5** Implement S3 upload with aioboto3
**Estimate:** 2h (реально полдня - multipart upload для больших файлов, error handling)

**T-1.6** Add DynamoDB write operations for URL metadata
**Estimate:** 3h (реально 1 день - batch writes, conditional updates, GSI проекции)

**T-1.7** Unit tests for downloader and storage services
**Estimate:** 4h (реально 1-2 дня - моки для AWS, async тесты, edge cases)

---

#### US-2: Content Deduplication

**T-2.1** Implement SHA-256 hashing for HTML content
**Estimate:** 1h (реально 3-4h - нормализация HTML, encoding issues, streaming для больших файлов)

**T-2.2** Create DynamoDB query by content_hash using GSI
**Estimate:** 2h (реально полдня - pagination, query optimization, eventually consistent reads)

**T-2.3** Add deduplication logic in downloader flow
**Estimate:** 3h (реально 1-2 дня - race conditions, distributed locks, transaction conflicts)

**T-2.4** Integration tests for deduplication scenarios
**Estimate:** 3h (реально 1 день - setup тестовой инфры, cleanup, parallel execution)

---

#### Infrastructure & DevOps

**T-3.1** Configure AWS credentials and IAM roles
**Estimate:** 2h (реально 1-2 дня - least privilege policies, cross-account access, debugging permissions)

**T-3.2** Setup S3 bucket with lifecycle policies
**Estimate:** 1h (реально полдня - CORS, versioning, encryption, bucket policies)

**T-3.3** Deploy DynamoDB table in test environment
**Estimate:** 1h (реально полдня - capacity planning, indexes, backup настройка)

**T-3.4** Configure Litestar app with environment variables
**Estimate:** 2h (реально полдня - secrets management, validation, defaults)

**T-3.5** Add logging and basic error handling
**Estimate:** 3h (реально 1-2 дня - structured logging, correlation IDs, error aggregation, alerts)

---

### Sprint Capacity
- Оптимистичная оценка: 40h
- Реальная оценка: 15-20 дней (3-4 недели)
- Факторы икс10: AWS permissions hell, async debugging, network issues, production incidents, meetings
- Рекомендация: взять 2-3 задачи максимум на спринт

### Definition of Done
- Code reviewed and merged to main
- Unit test coverage ≥80%
- Integration tests passing
- API documented in Swagger
- Deployed to test environment
- Acceptance criteria validated by PO
