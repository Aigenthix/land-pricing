#!/usr/bin/env python3
"""
Test script to verify local OCR functionality works correctly
"""

import os
import sys
from Fin_plsplspls import RobustLandRecordOCRDocTR

def test_ocr_with_sample_images():
    """Test OCR functionality with available sample images"""
    
    # Check if sample images exist
    sample_images_dir = "7_12 images"
    if not os.path.exists(sample_images_dir):
        print(f"Sample images directory '{sample_images_dir}' not found")
        return False
    
    # Get list of image files
    image_files = [f for f in os.listdir(sample_images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    if not image_files:
        print(f"No image files found in '{sample_images_dir}'")
        return False
    
    print(f"Found {len(image_files)} sample images")
    
    try:
        # Initialize OCR processor
        print("Initializing OCR processor...")
        ocr_processor = RobustLandRecordOCRDocTR()
        print("OCR processor initialized successfully!")
        
        # Test with first available image
        test_image = os.path.join(sample_images_dir, image_files[0])
        print(f"\nTesting OCR with: {test_image}")
        
        # Process the image
        results = ocr_processor.process_image(test_image)
        
        print(f"\nOCR Results:")
        print(f"- Total Cultivable Area: {results.get('total_cultivable_area', 'Not found')}")
        print(f"- Assessment: {results.get('assessment', 'Not found')}")
        
        # Test assessment value calculation
        if results.get('assessment') and results.get('total_cultivable_area'):
            try:
                assessment = float(results['assessment'])
                total_area = results['total_cultivable_area']
                
                # Handle format like '0.02.00' -> 0.02
                if total_area.count('.') > 1:
                    parts = total_area.split('.')
                    total_area_val = float(f"{parts[0]}.{parts[1]}")
                else:
                    total_area_val = float(total_area)
                
                calculated_assessment = assessment / total_area_val
                print(f"- Calculated Assessment Value: {calculated_assessment:.4f}")
                
                print("\n✅ OCR test completed successfully!")
                return True
                
            except (ValueError, ZeroDivisionError) as e:
                print(f"\n❌ Assessment calculation failed: {e}")
                return False
        else:
            print("\n⚠️  OCR completed but missing required values")
            return False
            
    except Exception as e:
        print(f"\n❌ OCR test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_ocr_with_sample_images()
    sys.exit(0 if success else 1)
