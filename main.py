# main.py - v3.0.1 Unified Architecture
# Tác giả: Narga
# Entry point với legacy workflow integration

import sys
import logging
from pathlib import Path

# Import legacy workflow
from src.workflow import run_translation_workflow
from src.configuration import load_all_configs


def main():
    """
    Main entry point - runs legacy v2.7 workflow.
    
    This provides the complete, battle-tested translation pipeline with:
    - Smart chunking
    - Context chaining
    - Auto-retry with Chinese detection
    - Verification mode
    - Text normalization
    - Detailed statistics and monitoring
    """
    try:
        print("=" * 80)
        print("📚 Novel Translator v3.0.1 - Production Ready")
        print("=" * 80)
        print()
        print("🔧 Loading configuration...")
        
        # Load all configs (API keys, prompts, guidelines, etc.)
        config_params = load_all_configs()
        
        print("✓ Configuration loaded")
        print()
        print("=" * 80)
        print("🌍 Starting Translation Workflow")
        print("=" * 80)
        print()
        
        # Run the proven v2.7 translation workflow
        run_translation_workflow(config_params)
        
        print()
        print("=" * 80)
        print("🎉 Translation Complete!")
        print("=" * 80)
        
        return 0
    
    except FileNotFoundError as e:
        logging.critical(f"❌ File not found: {e}")
        print(f"\n❌ Error: {e}")
        return 1
    
    except ValueError as e:
        logging.critical(f"❌ Configuration error: {e}")
        print(f"\n❌ Configuration error: {e}")
        return 1
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Translation interrupted by user")
        logging.warning("Translation interrupted by user")
        return 130
    
    except Exception as e:
        logging.critical(f"❌ Unexpected error: {e}", exc_info=True)
        print(f"\n❌ Unexpected error: {e}")
        print("Check log file for details")
        return 1


if __name__ == '__main__':
    sys.exit(main())
