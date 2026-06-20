from fastapi import APIRouter, HTTPException
from app.services.iot_pipeline import FullPipeline  # your pipeline class
import traceback

router = APIRouter(prefix="/iot", tags=["IOT Analytics"])

@router.post("/run")
async def run_iot_pipeline():
    """
    Runs the full IOT analytics pipeline and regenerates reports.json.
    """
    try:
        pipeline = FullPipeline()
        result = pipeline.run_full_pipeline()   # Make sure your class exposes this method
        
        return {
            "success": True,
            "message": "IOT Analysis successfully completed.",
            "report_generated": True,
            "details": result
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed: {str(e)}"
        )
