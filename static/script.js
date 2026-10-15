
/* ============================================================
   GLOBAL VARIABLES
============================================================ */

let editProductId = null;


/* ============================================================
   HELPER FUNCTIONS
============================================================ */

function getToken() {
    return localStorage.getItem("access_token");
}

function getRole() {
    return localStorage.getItem("role");
}


/* ============================================================
   LOGOUT
============================================================ */

function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("username");
    localStorage.removeItem("role");

    window.location.href = "/login-page";
}


/* ============================================================
   LOAD CURRENT USER
============================================================ */

async function loadCurrentUser() {
    const token = getToken();

    if (!token) {
        logout();
        return false;
    }

    try {
        const response = await fetch("/me", {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (response.status === 401) {
            logout();
            return false;
        }

        if (!response.ok) {
            alert("Unable to verify user details.");
            return false;
        }

        const user = await response.json();

        // Save verified user information
        localStorage.setItem("username", user.username);
        localStorage.setItem("role", user.role);

        // Display username and role
        document.getElementById("currentUsername").textContent =
            user.username;

        document.getElementById("currentRole").textContent =
            user.role;

        // Display the correct interface for the role
        setupRoleBasedUI();

        return true;

    } catch (error) {
        console.error("Error loading user:", error);
        alert("Unable to connect to server.");
        return false;
    }
}


/* ============================================================
   ADMIN / USER INTERFACE
============================================================ */

function setupRoleBasedUI() {
    const role = getRole();

    const adminSection = document.getElementById("adminSection");
    const actionsHeader = document.getElementById("actionsHeader");

    if (role === "admin") {
        adminSection.style.display = "block";
        actionsHeader.style.display = "table-cell";
    } else {
        adminSection.style.display = "none";
        actionsHeader.style.display = "none";
    }
}


/* ============================================================
   LOAD PRODUCTS
   Display consecutive serial numbers: 1, 2, 3...
   Keep actual database IDs for Edit/Delete.
============================================================ */

async function loadProducts() {
    const token = getToken();

    if (!token) {
        logout();
        return;
    }

    try {
        const response = await fetch("/products", {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (response.status === 401) {
            logout();
            return;
        }

        if (!response.ok) {
            alert("Unable to load products.");
            console.error("Products request failed:", response.status);
            return;
        }

        const products = await response.json();

        const table = document.getElementById("productTable");
        const role = getRole();

        // Remove old rows before reloading
        table.innerHTML = "";

        // Show a message if no products exist
        if (products.length === 0) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");

            cell.colSpan = role === "admin" ? 5 : 4;
            cell.textContent = "No products found.";

            row.appendChild(cell);
            table.appendChild(row);
            return;
        }

        // index + 1 gives continuous displayed numbers
        products.forEach(function (product, index) {
            const row = document.createElement("tr");

            // Display serial number instead of database ID
            const idCell = document.createElement("td");
            idCell.textContent = index + 1;
            row.appendChild(idCell);

            // Product name
            const nameCell = document.createElement("td");
            nameCell.textContent = product.product_name;
            row.appendChild(nameCell);

            // Product price
            const priceCell = document.createElement("td");
            priceCell.textContent = product.sell_price;
            row.appendChild(priceCell);

            // Product quantity
            const quantityCell = document.createElement("td");
            quantityCell.textContent = product.quantity;
            row.appendChild(quantityCell);

            // Admin-only actions
            if (role === "admin") {
                const actionsCell = document.createElement("td");

                // Edit button
                const editButton = document.createElement("button");
                editButton.type = "button";
                editButton.textContent = "Edit";

                editButton.addEventListener("click", function () {
                    editProduct(
                        product.product_id,
                        product.product_name,
                        product.sell_price,
                        product.quantity
                    );
                });

                // Delete button
                const deleteButton = document.createElement("button");
                deleteButton.type = "button";
                deleteButton.textContent = "Delete";

                deleteButton.addEventListener("click", function () {
                    deleteProduct(product.product_id);
                });

                actionsCell.appendChild(editButton);
                actionsCell.appendChild(deleteButton);

                row.appendChild(actionsCell);
            }

            table.appendChild(row);
        });

    } catch (error) {
        console.error("Error loading products:", error);
        alert("Unable to connect to server.");
    }
}


/* ============================================================
   ADD / UPDATE PRODUCT
============================================================ */

async function saveProduct(event) {
    event.preventDefault();

    if (getRole() !== "admin") {
        alert("Only admins can modify products.");
        return;
    }

    const token = getToken();

    if (!token) {
        logout();
        return;
    }

    const name = document.getElementById("productName").value.trim();

    const price = Number(
        document.getElementById("productPrice").value
    );

    const quantity = Number(
        document.getElementById("productQuantity").value
    );

    if (
        !name ||
        !Number.isFinite(price) ||
        price < 0 ||
        !Number.isInteger(quantity) ||
        quantity < 0
    ) {
        alert("Enter a valid product name, price, and quantity.");
        return;
    }

    const productData = {
        name: name,
        price: price,
        quantity: quantity
    };

    const isEditing = editProductId !== null;

    const url = isEditing
        ? `/products/${editProductId}`
        : "/products";

    try {
        const response = await fetch(url, {
            method: isEditing ? "PUT" : "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(productData)
        });

        if (response.status === 401) {
            logout();
            return;
        }

        if (response.status === 403) {
            alert("Admin access required.");
            return;
        }

        const data = await response.json();

        if (!response.ok) {
            alert(data.detail || "Product operation failed.");
            return;
        }

        alert(
            isEditing
                ? "Product updated successfully."
                : "Product added successfully."
        );

        resetProductForm();

        // Reload products and recalculate displayed serial numbers
        await loadProducts();

    } catch (error) {
        console.error("Error saving product:", error);
        alert("Unable to connect to server.");
    }
}


/* ============================================================
   EDIT PRODUCT
   Use the real database ID.
============================================================ */

function editProduct(
    productId,
    productName,
    productPrice,
    productQuantity
) {
    if (getRole() !== "admin") {
        alert("Only admins can edit products.");
        return;
    }

    // Store actual database ID, not displayed serial number
    editProductId = productId;

    document.getElementById("productName").value = productName;
    document.getElementById("productPrice").value = productPrice;
    document.getElementById("productQuantity").value = productQuantity;

    document.getElementById("submitButton").textContent = "Update Product";

    document.querySelector(".form-title").textContent = "Update Product";

    document.getElementById("adminSection").scrollIntoView({
        behavior: "smooth"
    });
}


/* ============================================================
   RESET PRODUCT FORM
============================================================ */

function resetProductForm() {
    editProductId = null;

    document.getElementById("productForm").reset();

    document.getElementById("submitButton").textContent = "Add Product";

    document.querySelector(".form-title").textContent =
        "Add / Update Product";
}


/* ============================================================
   DELETE PRODUCT
   Use the real database ID.
============================================================ */

async function deleteProduct(productId) {
    if (getRole() !== "admin") {
        alert("Only admins can delete products.");
        return;
    }

    const confirmed = confirm(
        "Are you sure you want to delete this product?"
    );

    if (!confirmed) {
        return;
    }

    const token = getToken();

    if (!token) {
        logout();
        return;
    }

    try {
        const response = await fetch(`/products/${productId}`, {
            method: "DELETE",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (response.status === 401) {
            logout();
            return;
        }

        if (response.status === 403) {
            alert("Admin access required.");
            return;
        }

        const data = await response.json();

        if (!response.ok) {
            alert(data.detail || "Unable to delete product.");
            return;
        }

        alert("Product deleted successfully.");

        // Reload the table; serial numbers will become consecutive
        await loadProducts();

    } catch (error) {
        console.error("Error deleting product:", error);
        alert("Unable to connect to server.");
    }
}


/* ============================================================
   PAGE INITIALIZATION
============================================================ */

document.addEventListener("DOMContentLoaded", async function () {
    document.getElementById("logoutButton").addEventListener(
        "click",
        logout
    );

    document.getElementById("productForm").addEventListener(
        "submit",
        saveProduct
    );

    const userLoaded = await loadCurrentUser();

    if (!userLoaded) {
        return;
    }

    await loadProducts();
});
