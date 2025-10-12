#!/usr/bin/env python3
"""
JSON Key Value Analyzer

Analyzes JSON data to count occurrences of values for a specific key.
Usage: python json_key_analyzer.py <key_name> <json_file1> [json_file2] [json_file3] ...
"""

import json
import sys
from collections import Counter
from typing import Any, Dict, List, Union


def extract_values_from_json(data: Any, target_key: str) -> List[Any]:
    """
    Recursively extract all values for a specific key from JSON data.
    
    Args:
        data: The JSON data (dict, list, or primitive)
        target_key: The key to search for
        
    Returns:
        List of all values found for the target key
    """
    values = []
    
    if isinstance(data, dict):
        # Check if current dict has the target key
        if target_key in data:
            values.append(data[target_key])
        
        # Recursively search in all values
        for value in data.values():
            values.extend(extract_values_from_json(value, target_key))
            
    elif isinstance(data, list):
        # Recursively search in all list items
        for item in data:
            values.extend(extract_values_from_json(item, target_key))
    
    return values


def analyze_json_key(json_file: str, key_name: str) -> Counter:
    """
    Analyze a JSON file and count occurrences of values for a specific key.
    
    Args:
        json_file: Path to the JSON file
        key_name: The key to analyze
        
    Returns:
        Counter object with the value counts
    """
    try:
        # Read and parse JSON file
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract all values for the target key
        values = extract_values_from_json(data, key_name)
        
        if not values:
            print(f"No values found for key '{key_name}' in {json_file}")
            return Counter()
        
        # Count occurrences
        counter = Counter(values)
        
        # Display results
        print(f"Analysis of key '{key_name}' in {json_file}")
        print("=" * 50)
        print(f"Total occurrences: {len(values)}")
        print(f"Unique values: {len(counter)}")
        print()
        
        # Sort by count (descending) then by value (ascending)
        sorted_items = sorted(counter.items(), key=lambda x: (-x[1], str(x[0])))
        
        print("Value counts:")
        print("-" * 30)
        for value, count in sorted_items:
            percentage = (count / len(values)) * 100
            print(f"{value!r:20} : {count:4d} ({percentage:5.1f}%)")
        
        # Show some statistics
        print()
        print("Statistics:")
        print("-" * 30)
        print(f"Most common: {counter.most_common(1)[0][0]!r} ({counter.most_common(1)[0][1]} times)")
        print(f"Least common: {min(counter.items(), key=lambda x: x[1])[0]!r} ({min(counter.items(), key=lambda x: x[1])[1]} times)")
        
        # Show value types
        type_counts = Counter(type(v).__name__ for v in values)
        print(f"Value types: {dict(type_counts)}")
        print()
        
        return counter
        
    except FileNotFoundError:
        print(f"Error: File '{json_file}' not found")
        return Counter()
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{json_file}': {e}")
        return Counter()
    except Exception as e:
        print(f"Error: {e}")
        return Counter()


def analyze_multiple_files(json_files: List[str], key_name: str) -> None:
    """
    Analyze multiple JSON files and provide both individual and combined summaries.
    
    Args:
        json_files: List of JSON file paths
        key_name: The key to analyze
    """
    all_counters = []
    file_results = {}
    
    # Analyze each file individually
    for json_file in json_files:
        print(f"\n{'='*60}")
        counter = analyze_json_key(json_file, key_name)
        all_counters.append(counter)
        file_results[json_file] = counter
    
    # Combine all results
    combined_counter = Counter()
    total_occurrences = 0
    
    for counter in all_counters:
        combined_counter.update(counter)
        total_occurrences += sum(counter.values())
    
    if not combined_counter:
        print(f"\n{'='*60}")
        print(f"No values found for key '{key_name}' in any of the provided files")
        return
    
    # Display combined results
    print(f"\n{'='*60}")
    print(f"COMBINED ANALYSIS of key '{key_name}' across {len(json_files)} files")
    print("=" * 60)
    print(f"Total occurrences: {total_occurrences}")
    print(f"Unique values: {len(combined_counter)}")
    print()
    
    # Sort by count (descending) then by value (ascending)
    sorted_items = sorted(combined_counter.items(), key=lambda x: (-x[1], str(x[0])))
    
    print("Combined value counts:")
    print("-" * 40)
    for value, count in sorted_items:
        percentage = (count / total_occurrences) * 100
        print(f"{value!r:25} : {count:6d} ({percentage:5.1f}%)")
    
    # Show some statistics
    print()
    print("Combined statistics:")
    print("-" * 40)
    print(f"Most common: {combined_counter.most_common(1)[0][0]!r} ({combined_counter.most_common(1)[0][1]} times)")
    print(f"Least common: {min(combined_counter.items(), key=lambda x: x[1])[0]!r} ({min(combined_counter.items(), key=lambda x: x[1])[1]} times)")
    
    # Show per-file breakdown for top values
    print()
    print("Per-file breakdown (top 5 values):")
    print("-" * 40)
    top_values = [item[0] for item in sorted_items[:5]]
    
    for value in top_values:
        print(f"\n{value!r}:")
        for json_file in json_files:
            count = file_results[json_file].get(value, 0)
            if count > 0:
                percentage = (count / sum(file_results[json_file].values())) * 100 if sum(file_results[json_file].values()) > 0 else 0
                print(f"  {json_file:30} : {count:4d} ({percentage:5.1f}%)")


def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 3:
        print("Usage: python json_key_analyzer.py <key_name> <json_file1> [json_file2] [json_file3] ...")
        print()
        print("Examples:")
        print("  python json_key_analyzer.py questionType data.json")
        print("  python json_key_analyzer.py field_type assessment1.json assessment2.json")
        print("  python json_key_analyzer.py target_type schema1.json schema2.json schema3.json")
        print()
        print("Single file analysis:")
        print("  python json_key_analyzer.py questionType data.json")
        print()
        print("Multiple file analysis:")
        print("  python json_key_analyzer.py questionType file1.json file2.json file3.json")
        sys.exit(1)
    
    key_name = sys.argv[1]
    json_files = sys.argv[2:]
    
    if len(json_files) == 1:
        # Single file analysis
        analyze_json_key(json_files[0], key_name)
    else:
        # Multiple file analysis
        analyze_multiple_files(json_files, key_name)


if __name__ == "__main__":
    main()
