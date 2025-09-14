async def run_simple_scrape_task(task_id: str, urls: List[str], max_pages: int = 20):
    scraper = SimpleProductScraper()
    all_results = []

    try:
        for url in urls:
            if "/collection" in url or "/category" in url:
                # ✅ Category/Collection → use pagination scraper
                products = await scraper.scrape_collection_with_pagination(url, max_pages=max_pages)
                all_results.extend(products)
            else:
                # ✅ Single product
                product = await scraper.extract_product_data(url)
                all_results.append(product)

        # Save result in active_tasks
        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result"] = {"products": all_results}
        active_tasks[task_id]["end_time"] = datetime.now().isoformat()
        active_tasks[task_id]["processing_time"] = (
            datetime.fromisoformat(active_tasks[task_id]["end_time"]) -
            datetime.fromisoformat(active_tasks[task_id]["start_time"])
        ).total_seconds()

    except Exception as e:
        logger.error(f"Error in scrape task {task_id}: {e}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)
        active_tasks[task_id]["end_time"] = datetime.now().isoformat()
