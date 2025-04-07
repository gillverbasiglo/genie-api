from fastapi.responses import JSONResponse
from fastapi import APIRouter

router = APIRouter(prefix="/.well-known", tags=["appleSiteAssociation"])

@router.get("/apple-app-site-association")
async def apple_app_site_association():
    # Create the AASA content
    aasa_content = {
        "applinks": {
            "apps": [],
            "details": [
                {
                    "appID": "64TH9648Q9.com.travel.genie", 
                    "paths": ["*"]
                }
            ]
        }
    }
    
    response = JSONResponse(content=aasa_content)
    response.headers["Content-Type"] = "application/json"
    
    response.headers["Cache-Control"] = "public, max-age=86400"
    
    return response
