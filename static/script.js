let editProductId = null;


// LOAD PRODUCTS
async function loadProducts() {

    const response = await fetch("/products");

    const products = await response.json();

    const table = document.getElementById("productTable");

    table.innerHTML = "";

    products.forEach(product => {

        const row = table.insertRow();

        row.insertCell(0).textContent = product.product_id;
        row.insertCell(1).textContent = product.product_name;
        row.insertCell(2).textContent = product.sell_price;
        row.insertCell(3).textContent = product.quantity;

        const actionCell = row.insertCell(4);


        // EDIT BUTTON
        const editButton = document.createElement("button");

        editButton.textContent = "Edit";

        editButton.onclick = function () {
            editProduct(product);
        };

        actionCell.appendChild(editButton);


        // DELETE BUTTON
        const deleteButton = document.createElement("button");

        deleteButton.textContent = "Delete";

        deleteButton.onclick = function () {
            deleteProduct(product.product_id);
        };

        actionCell.appendChild(deleteButton);
    });
}


// EDIT PRODUCT
function editProduct(product) {

    editProductId = product.product_id;

    document.getElementById("productName").value = product.product_name;

    document.getElementById("productPrice").value = product.sell_price;

    document.getElementById("productQuantity").value = product.quantity;

    document.getElementById("submitButton").textContent = "Update Product";
}


// DELETE PRODUCT
async function deleteProduct(productId) {

    const response = await fetch(`/products/${productId}`, {
        method: "DELETE"
    });

    const result = await response.json();

    console.log(result);

    loadProducts();
}


// ADD / UPDATE PRODUCT
document.getElementById("productForm").addEventListener("submit", async function (event) {

    event.preventDefault();

    const name = document.getElementById("productName").value;

    const price = document.getElementById("productPrice").value;

    const quantity = document.getElementById("productQuantity").value;

    let response;


    // UPDATE
    if (editProductId !== null) {

        response = await fetch(`/products/${editProductId}`, {

            method: "PUT",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                name: name,
                price: Number(price),
                quantity: Number(quantity)
            })
        });

    }


    // ADD
    else {

        response = await fetch("/products", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                name: name,
                price: Number(price),
                quantity: Number(quantity)
            })
        });
    }


    const result = await response.json();

    console.log(result);


    if (!response.ok) {

        alert("Operation failed");

        return;
    }


    if (editProductId !== null) {

        alert("Product updated successfully!");

    } else {

        alert("Product added successfully!");
    }


    document.getElementById("productForm").reset();

    document.getElementById("submitButton").textContent = "Add Product";

    editProductId = null;

    loadProducts();

});
loadProducts();