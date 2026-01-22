# Quick Start Guide

## Testing the Application

After setup, verify everything works:

```bash
# Run the test suite
python test_app.py
```

This will check:
- ✓ All imports work
- ✓ Configuration is valid
- ✓ Database can be initialized
- ✓ Logging system works
- ✓ Flask app and health endpoint work

## Starting the Application

### Development Mode
```bash
python run.py
```

The app will start on http://localhost:5001 (default)

### Production Mode
```bash
FLASK_ENV=production python run.py
```

**Important**: In production, you MUST set `FLASK_SECRET_KEY` in your `.env` file.

## Health Check

Once running, verify the application is healthy:

```bash
curl http://localhost:5001/api/health
```

Should return:
```json
{
  "status": "healthy",
  "service": "ai4sr",
  "timestamp": "2024-..."
}
```

## Common Issues

### Port Already in Use
Change the port in `.env`:
```
FLASK_PORT=5002
```

### Missing OPENAI_KEY
Add to `.env`:
```
OPENAI_KEY=sk-your-key-here
```

### Database Errors
Delete and recreate:
```bash
rm data/review.db
python run.py  # Will recreate automatically
```

## Next Steps

1. Open http://localhost:5001 in your browser
2. Configure your API key in Settings
3. Start a new project
4. Ask a research question!


