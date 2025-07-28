document.addEventListener('DOMContentLoaded', function() {
    function showDetails(spotId) { 
        const panel = document.getElementById("details-content");
        panel.innerHTML = `<p class="text-center text-muted">Loading details...</p>`;

        fetch(`/admin/spot-details/${spotId}`)
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errData => { throw new Error(errData.error || 'Failed to fetch details'); });
                }
                return response.json();
            })
            .then(data => {
                let htmlContent = '';

                // --- display current status and details ---
                if (data.current_occupied && data.current_booking_details) {
                    // scenario: spot is currently physically occupied
                    htmlContent += `
                        <h6 class="text-center">Currently Occupied</h6>
                        <p><strong>User:</strong> ${data.current_booking_details.user_name}</p>
                        <p><strong>Email:</strong> ${data.current_booking_details.email}</p>
                        <p><strong>Vehicle No:</strong> ${data.current_booking_details.vehicle_no}</p>
                        <p><strong>Start:</strong> ${data.current_booking_details.parking_time}</p>
                        <p><strong>Expiry:</strong> ${data.current_booking_details.leaving_time}</p>
                        <p><strong>Paid Cost:</strong> ₹${data.current_booking_details.parking_cost}</p>
                        <hr>
                    `;
                } else if (data.spot_status === 'O' && !data.current_occupied) {
                    // scenario: spot is 'O' in DB but no active booking found (e.g., just expired, or inconsistency)
                    htmlContent += `<p class="text-center text-danger">Spot is physically occupied but no active booking details found.</p><hr>`;
                } else {
                    // scenario: spot is 'A' in DB (truly available or booked for future)
                    htmlContent += `<p class="text-center text-success">Spot is currently Available.</p>`;
                    if (data.future_bookings_details.length > 0) {
                        // if it's 'A' but has future bookings, clarify this
                        htmlContent += `<p class="text-center text-muted">(Booked for future periods)</p>`;
                    }
                    htmlContent += `<hr>`; // add hr for separation
                }

                // --- display future bookings if available ---
                if (data.future_bookings_details && data.future_bookings_details.length > 0) {
                    htmlContent += `
                        <h6 class="text-center mt-3">Upcoming Bookings</h6>
                        <table class="future-bookings-table">
                            <thead>
                                <tr>
                                    <th>User</th>
                                    <th>Vehicle No</th>
                                    <th>From</th>
                                    <th>Until</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${data.future_bookings_details.map(fb => `
                                    <tr>
                                        <td>${fb.user_name}</td>
                                        <td>${fb.vehicle_no}</td>
                                        <td>${fb.parking_time}</td>
                                        <td>${fb.leaving_time}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `;
                } else if (!data.current_occupied) { // only show "no upcoming" if not currently occupied
                    htmlContent += `<p class="text-center text-muted">No upcoming bookings for this spot.</p>`;
                }

                // --- add delete button based on 'is_deletable' flag from backend ---
                if (data.is_deletable) { 
                    htmlContent += `
                        <div class="text-center mt-3">
                            <button class="btn btn-danger" onclick="deleteSpot(${spotId})">Delete Spot</button>
                        </div>
                    `;
                } else {
                    htmlContent += `
                        <div class="text-center mt-3 text-muted">
                            Spot cannot be deleted while it has active or future bookings.
                        </div>
                    `;
                }
                
                htmlContent += `<div class="text-center mt-3"><button class="btn btn-secondary" onclick="clearDetails()">Close</button></div>`;

                panel.innerHTML = htmlContent;

            })
            .catch(error => {
                console.error('Error fetching spot details:', error);
                panel.innerHTML = `<p class="text-danger">Error: ${error.message || 'Could not load details.'}</p>`;
            });
    }

    // clearDetails and deleteSpot functions) 
    function clearDetails() {
        document.getElementById("details-content").innerHTML = "Click a parking spot to view details here.";
    }

    function deleteSpot(spotId) {
        if (confirm('Are you sure you want to delete this spot?')) {
            fetch(`/admin/delete_spot/${spotId}`, { method: 'POST' })
                .then(response => {
                    if (response.ok) {
                        location.reload(); 
                    } else {
                        response.json().then(data => {
                            alert(data.error || 'Failed to delete spot.'); 
                        }).catch(() => { 
                            alert('Failed to delete spot. Server error.');
                        });
                    }
                })
                .catch(error => {
                    console.error('Error deleting spot:', error);
                    alert('An error occurred while trying to delete the spot.');
                });
        }
    }

    window.showDetails = showDetails;
    window.clearDetails = clearDetails;
    window.deleteSpot = deleteSpot;
});

