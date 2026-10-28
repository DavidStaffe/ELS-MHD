"""Do not echo submitted passwords/keys in request validation errors."""

from fastapi.responses import JSONResponse


async def validation_error(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {
                    "loc": list(error["loc"]),
                    "type": error["type"],
                    "msg": "Eingabe ungültig.",
                }
                for error in exc.errors()
            ]
        },
    )
