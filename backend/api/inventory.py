"""
Inventory API endpoints - Electronic components, PCB parts & storage management
Supports categories, specs, storage locations, stock tracking, and supplier links
"""

from flask import Blueprint, jsonify, request, send_file
import json
import os
import uuid
from datetime import datetime
import tempfile
import csv
import subprocess

bp = Blueprint('inventory', __name__)

INVENTORY_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'inventory.json')
CSV_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'WTl_Component_Inventory.csv')
ODS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'WTl_Component_Inventory.ods')

DEFAULT_CATEGORIES = [
    "Resistors",
    "Capacitors",
    "Semiconductors & ICs",
    "Microcontrollers & Modules",
    "Diodes & LEDs",
    "Connectors & Headers",
    "Custom PCBs",
    "Hardware & Fasteners",
    "Sensors",
    "Other"
]

def ensure_inventory_file():
    """Ensure inventory data file and directory exist with empty items list if missing"""
    os.makedirs(os.path.dirname(INVENTORY_FILE), exist_ok=True)
    if not os.path.exists(INVENTORY_FILE) or os.path.getsize(INVENTORY_FILE) == 0:
        initial_data = {
            "categories": DEFAULT_CATEGORIES,
            "items": []
        }
        save_inventory(initial_data)

def load_inventory():
    """Load inventory from JSON file"""
    ensure_inventory_file()
    try:
        with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "items" not in data:
                data["items"] = []
            if "categories" not in data:
                data["categories"] = DEFAULT_CATEGORIES
            return data
    except Exception as e:
        print(f"Error loading inventory: {e}")
        return {"items": [], "categories": DEFAULT_CATEGORIES}

def save_inventory(data):
    """Safely save inventory data atomically"""
    dir_name = os.path.dirname(INVENTORY_FILE)
    os.makedirs(dir_name, exist_ok=True)
    try:
        # Write to temporary file first
        with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding='utf-8') as tf:
            json.dump(data, tf, indent=2, ensure_ascii=False)
            temp_name = tf.name
        try:
            os.chmod(temp_name, 0o664)
        except Exception:
            pass
        # Atomic replace
        os.replace(temp_name, INVENTORY_FILE)
        # Keep spreadsheets synchronized
        try:
            generate_spreadsheets(data)
        except Exception as se:
            print(f"Spreadsheet sync error: {se}")
        return True
    except Exception as e:
        print(f"Error saving inventory: {e}")
        if 'temp_name' in locals() and os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except:
                pass
        return False

@bp.route('', methods=['GET'])
def get_inventory():
    """List inventory items with search and filter capabilities"""
    try:
        data = load_inventory()
        items = data.get("items", [])

        # Filters
        category = request.args.get('category', '').strip()
        search = request.args.get('search', '').strip().lower()
        location = request.args.get('location', '').strip()
        low_stock_only = request.args.get('low_stock', '').lower() in ('true', '1', 'yes')

        filtered = []
        total_value = 0.0
        low_stock_count = 0

        for item in items:
            qty = int(item.get('quantity', 0))
            min_qty = int(item.get('min_quantity', 5))
            price = float(item.get('price', 0.0) or 0.0)
            total_value += qty * price

            is_low = qty <= min_qty
            if is_low:
                low_stock_count += 1

            # Check Category Filter
            if category and category.lower() != 'all' and item.get('category', '').lower() != category.lower():
                continue

            # Check Location Filter
            if location and location.lower() != 'all' and item.get('location', '').lower() != location.lower():
                continue

            # Check Low Stock Filter
            if low_stock_only and not is_low:
                continue

            # Check Search Query (searches name, value, package, location, manufacturer, mpn, notes)
            if search:
                searchable = " ".join([
                    item.get('name', ''),
                    item.get('category', ''),
                    item.get('value', ''),
                    item.get('package', ''),
                    item.get('location', ''),
                    item.get('manufacturer', ''),
                    item.get('mpn', ''),
                    item.get('notes', '')
                ]).lower()
                if search not in searchable:
                    continue

            filtered.append(item)

        # Sort by updated_at descending
        filtered.sort(key=lambda x: x.get('updated_at', x.get('created_at', '')), reverse=True)

        return jsonify({
            'items': filtered,
            'total_items_count': len(items),
            'filtered_count': len(filtered),
            'low_stock_count': low_stock_count,
            'total_inventory_value': round(total_value, 2),
            'categories': data.get('categories', DEFAULT_CATEGORIES)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('', methods=['POST'])
def add_item():
    """Add a new component to inventory"""
    try:
        body = request.get_json() or {}
        name = body.get('name', '').strip()
        if not name:
            return jsonify({'error': 'Component name is required'}), 400

        data = load_inventory()
        items = data.get('items', [])
        categories = data.get('categories', DEFAULT_CATEGORIES)

        category = body.get('category', 'Other').strip() or 'Other'
        if category not in categories:
            categories.append(category)

        now = datetime.now().isoformat()
        new_item = {
            'id': f"comp-{uuid.uuid4().hex[:8]}",
            'name': name,
            'category': category,
            'value': body.get('value', '').strip(),
            'package': body.get('package', '').strip(),
            'location': body.get('location', '').strip(),
            'quantity': max(0, int(body.get('quantity', 0) or 0)),
            'min_quantity': max(0, int(body.get('min_quantity', 5) or 5)),
            'price': max(0.0, float(body.get('price', 0.0) or 0.0)),
            'manufacturer': body.get('manufacturer', '').strip(),
            'mpn': body.get('mpn', '').strip(),
            'purchase_url': body.get('purchase_url', '').strip(),
            'datasheet_url': body.get('datasheet_url', '').strip(),
            'notes': body.get('notes', '').strip(),
            'created_at': now,
            'updated_at': now
        }

        items.insert(0, new_item)
        data['items'] = items
        data['categories'] = categories

        if save_inventory(data):
            return jsonify({'success': True, 'item': new_item}), 201
        else:
            return jsonify({'error': 'Failed to save component to storage'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<item_id>', methods=['GET'])
def get_item(item_id):
    """Get single component details"""
    try:
        data = load_inventory()
        for item in data.get('items', []):
            if item.get('id') == item_id:
                return jsonify(item)
        return jsonify({'error': 'Component not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<item_id>', methods=['PUT'])
def update_item(item_id):
    """Update existing component"""
    try:
        body = request.get_json() or {}
        data = load_inventory()
        items = data.get('items', [])
        categories = data.get('categories', DEFAULT_CATEGORIES)

        target = None
        for item in items:
            if item.get('id') == item_id:
                target = item
                break

        if not target:
            return jsonify({'error': 'Component not found'}), 404

        name = body.get('name', target.get('name')).strip()
        if not name:
            return jsonify({'error': 'Component name cannot be empty'}), 400

        category = body.get('category', target.get('category', 'Other')).strip()
        if category and category not in categories:
            categories.append(category)

        target['name'] = name
        target['category'] = category
        target['value'] = body.get('value', target.get('value', '')).strip()
        target['package'] = body.get('package', target.get('package', '')).strip()
        target['location'] = body.get('location', target.get('location', '')).strip()
        target['quantity'] = max(0, int(body.get('quantity', target.get('quantity', 0)) or 0))
        target['min_quantity'] = max(0, int(body.get('min_quantity', target.get('min_quantity', 5)) or 5))
        target['price'] = max(0.0, float(body.get('price', target.get('price', 0.0)) or 0.0))
        target['manufacturer'] = body.get('manufacturer', target.get('manufacturer', '')).strip()
        target['mpn'] = body.get('mpn', target.get('mpn', '')).strip()
        target['purchase_url'] = body.get('purchase_url', target.get('purchase_url', '')).strip()
        target['datasheet_url'] = body.get('datasheet_url', target.get('datasheet_url', '')).strip()
        target['notes'] = body.get('notes', target.get('notes', '')).strip()
        target['updated_at'] = datetime.now().isoformat()

        data['categories'] = categories
        if save_inventory(data):
            return jsonify({'success': True, 'item': target})
        else:
            return jsonify({'error': 'Failed to save updated component'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<item_id>/stock', methods=['PATCH'])
def adjust_stock(item_id):
    """Quick stock quantity adjustment (+/- delta or direct set)"""
    try:
        body = request.get_json() or {}
        data = load_inventory()
        items = data.get('items', [])

        target = None
        for item in items:
            if item.get('id') == item_id:
                target = item
                break

        if not target:
            return jsonify({'error': 'Component not found'}), 404

        current_qty = int(target.get('quantity', 0))

        if 'delta' in body:
            delta = int(body.get('delta', 0))
            new_qty = max(0, current_qty + delta)
        elif 'quantity' in body:
            new_qty = max(0, int(body.get('quantity', 0)))
        else:
            return jsonify({'error': 'Missing delta or quantity in request'}), 400

        target['quantity'] = new_qty
        target['updated_at'] = datetime.now().isoformat()

        if save_inventory(data):
            return jsonify({'success': True, 'id': item_id, 'quantity': new_qty})
        else:
            return jsonify({'error': 'Failed to save stock adjustment'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<item_id>', methods=['DELETE'])
def delete_item(item_id):
    """Delete a component from inventory"""
    try:
        data = load_inventory()
        items = data.get('items', [])
        initial_len = len(items)

        items = [item for item in items if item.get('id') != item_id]

        if len(items) == initial_len:
            return jsonify({'error': 'Component not found'}), 404

        data['items'] = items
        if save_inventory(data):
            return jsonify({'success': True, 'deleted_id': item_id})
        else:
            return jsonify({'error': 'Failed to delete component'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/categories', methods=['GET'])
def get_categories():
    """Get category list with part counts"""
    try:
        data = load_inventory()
        items = data.get('items', [])
        categories = data.get('categories', DEFAULT_CATEGORIES)

        counts = {}
        for c in categories:
            counts[c] = 0
        for item in items:
            cat = item.get('category', 'Other')
            counts[cat] = counts.get(cat, 0) + 1

        result = [{'name': cat, 'count': counts.get(cat, 0)} for cat in categories]
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/locations', methods=['GET'])
def get_locations():
    """Get distinct storage locations"""
    try:
        data = load_inventory()
        items = data.get('items', [])
        locations = sorted(list({item.get('location').strip() for item in items if item.get('location', '').strip()}))
        return jsonify(locations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/export', methods=['GET'])
def export_inventory():
    """Export the inventory as a downloadable JSON file"""
    ensure_inventory_file()
    return send_file(
        INVENTORY_FILE,
        as_attachment=True,
        download_name=f"wtl-inventory-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mimetype='application/json'
    )

@bp.route('/import', methods=['POST'])
def import_inventory():
    """Import inventory from JSON backup (options: 'merge' or 'replace')"""
    try:
        mode = request.args.get('mode', 'merge') # merge or replace
        incoming = request.get_json() or {}

        incoming_items = incoming.get('items')
        if not isinstance(incoming_items, list):
            return jsonify({'error': 'Invalid format: items list expected'}), 400

        data = load_inventory()
        if mode == 'replace':
            data['items'] = incoming_items
            if 'categories' in incoming:
                data['categories'] = incoming['categories']
        else:
            # Merge by ID or append
            existing_ids = {item.get('id'): item for item in data.get('items', [])}
            for inc in incoming_items:
                inc_id = inc.get('id')
                if inc_id and inc_id in existing_ids:
                    existing_ids[inc_id].update(inc)
                else:
                    if not inc_id:
                        inc['id'] = f"comp-{uuid.uuid4().hex[:8]}"
                    data['items'].append(inc)

            if 'categories' in incoming and isinstance(incoming['categories'], list):
                for cat in incoming['categories']:
                    if cat not in data['categories']:
                        data['categories'].append(cat)

        if save_inventory(data):
            return jsonify({'success': True, 'total_items': len(data['items'])})
        else:
            return jsonify({'error': 'Failed to save imported inventory'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_spreadsheets(data=None):
    """Generate both CSV and native LibreOffice ODS spreadsheets for all inventory components"""
    try:
        if data is None:
            data = load_inventory()
        items = data.get('items', [])
        os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
        
        headers = [
            'Component Name', 'Category', 'Value / Spec', 'Package / Footprint',
            'Storage Location', 'Quantity in Stock', 'Min Threshold', 'Status',
            'Unit Price (€)', 'Total Value (€)', 'Manufacturer', 'MPN',
            'Purchase URL', 'Datasheet URL', 'Notes', 'Item ID', 'Last Updated'
        ]

        with open(CSV_FILE, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for item in items:
                qty = int(item.get('quantity', 0))
                min_qty = int(item.get('min_quantity', 5))
                price = float(item.get('price', 0.0) or 0.0)
                tot_val = round(qty * price, 2)
                status = 'OUT OF STOCK' if qty == 0 else ('LOW STOCK' if qty <= min_qty else 'IN STOCK')
                writer.writerow([
                    item.get('name', ''),
                    item.get('category', ''),
                    item.get('value', ''),
                    item.get('package', ''),
                    item.get('location', ''),
                    qty,
                    min_qty,
                    status,
                    f'{price:.3f}',
                    f'{tot_val:.2f}',
                    item.get('manufacturer', ''),
                    item.get('mpn', ''),
                    item.get('purchase_url', ''),
                    item.get('datasheet_url', ''),
                    item.get('notes', ''),
                    item.get('id', ''),
                    item.get('updated_at', '')
                ])
        
        # Convert to native LibreOffice ODS format if libreoffice is available
        try:
            outdir = os.path.dirname(ODS_FILE)
            subprocess.run([
                'libreoffice', '--headless', '--convert-to', 'ods',
                '--outdir', outdir, CSV_FILE
            ], capture_output=True, text=True, timeout=20)
        except Exception as e:
            print(f"Error converting to ODS: {e}")

        return True
    except Exception as e:
        print(f"Error generating spreadsheets: {e}")
        return False

@bp.route('/spreadsheet', methods=['GET'])
def get_spreadsheet():
    """Download the component inventory spreadsheet as ODS or CSV"""
    fmt = request.args.get('format', 'ods').lower()
    if not os.path.exists(CSV_FILE) or not os.path.exists(ODS_FILE):
        generate_spreadsheets()

    if fmt == 'csv':
        return send_file(
            CSV_FILE,
            as_attachment=True,
            download_name='WTl_Component_Inventory.csv',
            mimetype='text/csv'
        )
    else:
        if os.path.exists(ODS_FILE):
            return send_file(
                ODS_FILE,
                as_attachment=True,
                download_name='WTl_Component_Inventory.ods',
                mimetype='application/vnd.oasis.opendocument.spreadsheet'
            )
        else:
            return send_file(
                CSV_FILE,
                as_attachment=True,
                download_name='WTl_Component_Inventory.csv',
                mimetype='text/csv'
            )

@bp.route('/open-calc', methods=['POST'])
def open_in_calc():
    """Launch LibreOffice Calc on the desktop with the inventory spreadsheet"""
    try:
        if not os.path.exists(ODS_FILE):
            generate_spreadsheets()
        target_path = os.path.abspath(ODS_FILE if os.path.exists(ODS_FILE) else CSV_FILE)

        calc_bin = '/usr/bin/localc' if os.path.exists('/usr/bin/localc') else '/usr/bin/libreoffice'
        subprocess.Popen([calc_bin, target_path],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return jsonify({'status': 'opened', 'file': target_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
