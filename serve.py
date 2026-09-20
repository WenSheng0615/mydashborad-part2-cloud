"""Production launcher: explicit schema validation, one worker, no reload."""
import os
import uvicorn
from check_database import check_database

if __name__ == '__main__':
    check_database()
    uvicorn.run('main:app', host='0.0.0.0', port=int(os.getenv('PORT', '8000')),
                workers=1, reload=False)
