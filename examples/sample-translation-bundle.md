> Example `@code-translator` output. Frozen sample — a read-only, documentation-grounded
> translation **context bundle** (the agent writes nothing; this is what it hands back to
> the user or the `/orchestrator` flow). Source is a small Ruby on Rails slice translated to
> Python; languages are illustrative.

# Translation bundle — Rails → FastAPI

```
SOURCE  Ruby on Rails 7.1  →  TARGET  Python / FastAPI 0.115 + SQLAlchemy 2.0   [assumed — see NEEDS INPUT]
Granularity: file (1 controller + 1 model slice)
```

## Source (Ruby on Rails)

```ruby
# app/models/product.rb
class Product < ApplicationRecord
  belongs_to :store
  validates :name, presence: true
  validates :price_cents, numericality: { greater_than: 0 }
  scope :active, -> { where(archived_at: nil) }
end

# app/controllers/products_controller.rb
class ProductsController < ApplicationController
  def index
    products = Product.active.where(store_id: params[:store_id]).order(:name)
    render json: products.limit(params.fetch(:limit, 25))
  end
end
```

## Translation — Python / FastAPI + SQLAlchemy 2.0

```python
# models.py
from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase): ...

class Product(Base):
    __tablename__ = "products"
    id:           Mapped[int]      = mapped_column(primary_key=True)
    store_id:     Mapped[int]      = mapped_column(ForeignKey("stores.id"))
    name:         Mapped[str]      = mapped_column(String, nullable=False)
    price_cents:  Mapped[int]      = mapped_column(Integer)
    archived_at:  Mapped[str|None] = mapped_column(DateTime, nullable=True)
    store = relationship("Store")

# schemas.py
from pydantic import BaseModel, field_validator

class ProductIn(BaseModel):          # ← Rails validations become a Pydantic model
    name: str
    price_cents: int
    @field_validator("name")
    @classmethod
    def name_present(cls, v):
        if not v or not v.strip(): raise ValueError("name can't be blank")
        return v
    @field_validator("price_cents")
    @classmethod
    def price_positive(cls, v):
        if v <= 0: raise ValueError("price_cents must be greater than 0")
        return v

# routers/products.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter()

@router.get("/stores/{store_id}/products")
def index(store_id: int, limit: int = 25, db: Session = Depends(get_db)):
    stmt = (select(Product)
            .where(Product.store_id == store_id, Product.archived_at.is_(None))  # ← scope :active
            .order_by(Product.name)
            .limit(limit))
    return db.execute(stmt).scalars().all()
```

## Idiom map (cited)

| Rails | FastAPI / SQLAlchemy | source of truth |
| --- | --- | --- |
| `belongs_to :store` | `relationship("Store")` + `ForeignKey` | ctx7: sqlalchemy/sqlalchemy §relationships |
| `validates ...` | Pydantic `field_validator` on a schema | ctx7: pydantic/pydantic §validators |
| `scope :active -> where(archived_at: nil)` | `.where(Product.archived_at.is_(None))` | ctx7: sqlalchemy §`select()` / IS NULL |
| `params[:store_id]` | path param `store_id: int` | ctx7: fastapi §path-parameters |
| `params.fetch(:limit, 25)` | query param `limit: int = 25` | ctx7: fastapi §query-parameters |
| `render json: …` | return ORM objects (FastAPI serializes) | ctx7: fastapi §response-model |

## Docs consulted

- context7: `fastapi/fastapi@0.115`, `sqlalchemy/sqlalchemy@2.0`, `pydantic/pydantic@2`
- context7: `rails/rails@7.1` (source-side: ActiveRecord query + validation semantics)
- web: none required

## Caveats / open decisions

- **No 1:1 for `ApplicationController` filters** (auth, `current_organization` tenant scoping) — Rails hides these in a base controller; in FastAPI they become explicit `Depends(...)`. Not shown here; flag for the port.
- **Serialization**: returning ORM objects relies on a `response_model` / `from_attributes` config not shown — confirm before relying on it.
- **Validation timing**: Rails validates on save; the Pydantic model validates on *input*. Equivalent for a create endpoint, but not a behavioral identity for all paths.

## NEEDS INPUT

- **Target Python web framework** — defaulted to **FastAPI** (closest modern analog for a JSON API). Confirm, or say the word for **Django** (closest full-MVC analog, ActiveRecord↔Django ORM) or **Flask**. This materially changes the ORM + routing translation.

## Next step

Use as-is, or hand this bundle to **`/orchestrator`** as the grounding input for a gated port
(`@architect` plans from it → `@developer` implements under the commit/push gates). This agent
itself writes nothing.
