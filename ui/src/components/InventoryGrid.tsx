

interface Item {
  id: string;
  name: string;
  quantity: number;
  icon?: string;
}

interface InventoryGridProps {
  items: Item[];
}

export function InventoryGrid({ items }: InventoryGridProps) {
  return (
    <div className="inventory-grid">
      <h3>Inventory</h3>
      <div className="grid">
        {items.map((item) => (
          <div key={item.id} className="inventory-slot">
            <div className="item-icon">{item.icon || '📦'}</div>
            <div className="item-name">{item.name}</div>
            <div className="item-qty">×{item.quantity}</div>
          </div>
        ))}
        {items.length === 0 && <div className="empty">Empty</div>}
      </div>
    </div>
  );
}