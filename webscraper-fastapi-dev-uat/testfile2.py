async def run_simple_scrape_task(task_id: str, urls: List[str], max_pages: int):
    """Run the simple scraping task in the background"""
    start_time = time.time()
    
    try:
        active_tasks[task_id]["status"] = "running"
        
        async def progress_callback(progress_data):
            if task_id in active_tasks:
                active_tasks[task_id]["current_progress"] = {
                    **progress_data,
                    "timestamp": datetime.now().isoformat()
                }
                # Send real-time update via WebSocket
                await manager.send_progress_update(task_id, {
                    "type": "progress_update",
                    "data": progress_data
                })
        
        # result = await scrape_urls_simple_api(
        #     urls=urls,
        #     max_pages=max_pages,
        #     progress_callback=progress_callback
        # )
        all_results = []
        scraper = SimpleProductScraper()

        for url in urls:
            if "/collection" in url or "/category" in url:
                products = await scraper.scrape_collection_with_pagination(
                    url, max_pages=max_pages
                )
                all_results.extend(products)
            else:
                product = await scraper.extract_product_data(url)
                all_results.append(product)

        # Wrap in same structure scrape_urls_simple_api returned
        result = {"products": all_results, "metadata": {"timestamp": datetime.now().isoformat()}}

        # Update progress for post-processing
        active_tasks[task_id]["current_progress"] = {
            "stage": "post_processing",
            "percentage": 95,
            "details": "🔧 Post-processing and fixing image URLs...",
            "timestamp": datetime.now().isoformat()
        }
        await manager.send_progress_update(task_id, {
            "type": "progress_update",
            "data": active_tasks[task_id]["current_progress"]
        })
        
        # Post-process the scraped data (fix image URLs, etc.)
        result = post_process_scraped_data(result)
        
        # Save the fixed results automatically
        timestamp = result.get("metadata", {}).get("timestamp", datetime.now().strftime("%Y%m%d_%H%M%S"))
        await save_fixed_results(result, timestamp, task_id)
        
        # Update task with results
        active_tasks[task_id].update({
            "status": "completed",
            "result": result,
            "end_time": datetime.now().isoformat(),
            "processing_time": round(time.time() - start_time, 2)
        })
        
        # Send completion update via WebSocket
        await manager.send_progress_update(task_id, {
            "type": "task_completed",
            "data": active_tasks[task_id]
        })
        
    except Exception as e:
        logger.error(f"Simple scrape task {task_id} failed: {e}")
        active_tasks[task_id].update({
            "status": "failed",
            "error": str(e),
            "end_time": datetime.now().isoformat(),
            "processing_time": round(time.time() - start_time, 2)
        })
        
        # Send error update via WebSocket
        await manager.send_progress_update(task_id, {
            "type": "task_failed",
            "data": active_tasks[task_id]
        })