#!/usr/bin/env python3
"""
Test script specifically for Azure OpenAI embeddings access and permissions.
This helps diagnose permission issues with embeddings.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def test_embedding_permissions():
    """Test embeddings with detailed permission diagnostics."""
    print("\n" + "="*70)
    print("AZURE OPENAI EMBEDDINGS PERMISSION TEST")
    print("="*70)
    
    # Get configuration
    ai_project_endpoint = os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")
    direct_endpoint = os.getenv("AZURE_OPENAI_DIRECT_ENDPOINT")
    deployment_name = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")
    
    # If direct endpoint not set, try the known endpoint
    if not direct_endpoint:
        # Try to extract from AI Projects endpoint
        if ai_project_endpoint and "services.ai.azure.com" in ai_project_endpoint:
            from urllib.parse import urlparse
            try:
                parsed = urlparse(ai_project_endpoint)
                hostname = parsed.hostname
                if hostname:
                    subdomain = hostname.split('.')[0]
                    direct_endpoint = f"https://{subdomain}.cognitiveservices.azure.com"
                    print(f"\n  Note: Auto-extracted direct endpoint: {direct_endpoint}")
            except Exception:
                pass
    
    # Default to the known endpoint if still not set
    if not direct_endpoint:
        direct_endpoint = "https://oai-ai4sr.cognitiveservices.azure.com"
        print(f"\n  Note: Using default direct endpoint: {direct_endpoint}")
        print(f"  (Set AZURE_OPENAI_DIRECT_ENDPOINT in .env to override)")
    
    print(f"\nConfiguration:")
    print(f"  AI Projects Endpoint: {ai_project_endpoint or 'NOT SET'}")
    print(f"  Direct Endpoint: {direct_endpoint}")
    print(f"  Deployment Name: {deployment_name}")
    
    # Test 1: Try direct client
    print("\n" + "-"*70)
    print("TEST 1: Direct Azure OpenAI Client (cognitiveservices.azure.com)")
    print("-"*70)
    
    try:
        from agents.azure_config import get_embedding_client, get_embedding
        from azure.identity import DefaultAzureCredential
        
        # Get current user
        try:
            credential = DefaultAzureCredential()
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            print(f"  ✓ Authentication successful")
            print(f"  Token expires: {token.expires_on}")
        except Exception as auth_error:
            print(f"  ✗ Authentication failed: {auth_error}")
            print(f"\n  Please authenticate with: az login")
            return False
        
        # Try to create direct client
        try:
            # Temporarily set the endpoint if not already set
            original_endpoint = os.getenv("AZURE_OPENAI_DIRECT_ENDPOINT")
            if not original_endpoint and direct_endpoint:
                os.environ["AZURE_OPENAI_DIRECT_ENDPOINT"] = direct_endpoint
                print(f"  Setting AZURE_OPENAI_DIRECT_ENDPOINT={direct_endpoint} for this test")
            
            client = get_embedding_client()
            print(f"  ✓ Direct client created successfully")
            
            # Check what endpoint was actually used
            if hasattr(client, 'base_url') or hasattr(client, '_client'):
                try:
                    actual_endpoint = getattr(client, 'base_url', None) or getattr(client._client, 'base_url', None)
                    if actual_endpoint:
                        print(f"  Client endpoint: {actual_endpoint}")
                except:
                    pass
        except Exception as e:
            print(f"  ✗ Failed to create direct client: {e}")
            print(f"\n  This might indicate endpoint configuration issues.")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Restore original endpoint if we changed it
            if not original_endpoint and direct_endpoint:
                if original_endpoint is None:
                    os.environ.pop("AZURE_OPENAI_DIRECT_ENDPOINT", None)
                else:
                    os.environ["AZURE_OPENAI_DIRECT_ENDPOINT"] = original_endpoint
        
        # Try embedding call
        try:
            print(f"\n  Testing embedding call...")
            embedding = get_embedding("test text for embedding")
            print(f"  ✓ Embedding successful!")
            print(f"  Embedding dimension: {len(embedding)}")
            print(f"  First 5 values: {embedding[:5]}")
            return True
        except Exception as e:
            error_str = str(e)
            print(f"  ✗ Embedding call failed: {error_str}")
            
            # Check for specific permission errors
            if "401" in error_str or "PermissionDenied" in error_str or "Permission" in error_str:
                print(f"\n  ⚠️  PERMISSION ERROR DETECTED")
                print(f"\n  You need permissions on the Azure Cognitive Services resource.")
                print(f"\n  Required permission:")
                print(f"    Microsoft.CognitiveServices/accounts/OpenAI/deployments/embeddings/action")
                print(f"\n  How to grant:")
                print(f"    1. Go to Azure Portal")
                print(f"    2. Navigate to your Cognitive Services resource (not the AI Project)")
                print(f"       Resource name: oai-ai4sr")
                print(f"       Endpoint: https://oai-ai4sr.cognitiveservices.azure.com")
                print(f"    3. Go to Access Control (IAM)")
                print(f"    4. Add role assignment: 'Cognitive Services OpenAI User'")
                print(f"    5. Assign to: bushth@ext.euda.europa.eu")
                print(f"    6. Wait 2-5 minutes for permissions to propagate")
                print(f"\n  Alternative: Use Azure CLI:")
                print(f"    az role assignment create \\")
                print(f"      --role 'Cognitive Services OpenAI User' \\")
                print(f"      --assignee bushth@ext.euda.europa.eu \\")
                print(f"      --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/oai-ai4sr")
            elif "404" in error_str or "NotFound" in error_str:
                print(f"\n  ⚠️  DEPLOYMENT NOT FOUND")
                print(f"  The deployment '{deployment_name}' doesn't exist at the direct endpoint.")
                print(f"  Check that the deployment name is correct.")
            else:
                print(f"\n  Unexpected error. Full details:")
                import traceback
                traceback.print_exc()
            
            return False
            
    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ai_projects_client():
    """Test embeddings via AI Projects client as fallback."""
    print("\n" + "-"*70)
    print("TEST 2: AI Projects Client (fallback)")
    print("-"*70)
    
    try:
        from agents.azure_config import get_azure_client
        
        client = get_azure_client()
        deployment_name = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")
        
        print(f"  Testing embedding via AI Projects client...")
        response = client.embeddings.create(
            model=deployment_name,
            input="test text"
        )
        
        if response.data:
            print(f"  ✓ AI Projects client embedding successful!")
            print(f"  Embedding dimension: {len(response.data[0].embedding)}")
            return True
        else:
            print(f"  ✗ No data in response")
            return False
            
    except Exception as e:
        error_str = str(e)
        print(f"  ✗ AI Projects client failed: {error_str}")
        
        if "404" in error_str:
            print(f"  Note: Embeddings may not be accessible via AI Projects API path")
            print(f"  This is expected for GlobalStandard deployments")
        
        return False


def main():
    """Run embedding permission tests."""
    print("\n" + "="*70)
    print("EMBEDDING PERMISSIONS DIAGNOSTIC TOOL")
    print("="*70)
    print("\nThis script tests your access to Azure OpenAI embeddings")
    print("and helps diagnose permission issues.\n")
    
    # Test direct client (primary method)
    direct_success = test_embedding_permissions()
    
    # Test AI Projects client (fallback)
    ai_projects_success = test_ai_projects_client()
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    if direct_success:
        print("  ✓ Direct client: WORKING")
        print("\n  Your embeddings are configured correctly!")
    else:
        print("  ✗ Direct client: FAILED")
        print("\n  Action required:")
        print("  1. Grant 'Cognitive Services OpenAI User' role on the Cognitive Services resource")
        print("  2. Resource: Azure Portal → Cognitive Services → oai-ai4sr")
        print("  3. Wait 2-5 minutes for permissions to propagate")
        print("  4. Re-run this test: python test_embeddings.py")
    
    if ai_projects_success:
        print("  ✓ AI Projects client: WORKING (fallback)")
    else:
        print("  ✗ AI Projects client: FAILED (expected for GlobalStandard deployments)")
    
    print("\n" + "="*70)
    
    return direct_success or ai_projects_success


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

