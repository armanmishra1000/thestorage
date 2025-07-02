1.  frontend is not connecting with backend??
:: netstat -ano -p TCP | findstr ":5000"
:: taskkill /PID 7584 /F
:: than restart server and celery worker : 
	python -m uvicorn app.main:app --host 0.0.0.0 --port 5000
	celery -A app.celery_worker.celery_app worker --loglevel=info -P solo