// general server stuff

import {API, getIdToken} from './actions';
import {isArray} from 'lodash';

function jsonResponse(response) {
  if (!response.ok) {
    const error = new Error();
    error.status = response.status;
    return Promise.reject(error);
  }
  return response.json();
}

export class RestServerApi {
  getUserPromise() {
    return fetch(API + '/user', {
      headers: {
        Authorization: 'Bearer ' + getIdToken(),
        'Content-Type': 'application/json',
      },
    }).then((response) => jsonResponse(response));
  }

  getDatasetsPromise() {
    return fetch(API + '/datasets', {
      headers: {Authorization: 'Bearer ' + getIdToken()},
    }).then((response) => jsonResponse(response));
  }

  deleteDatasetPromise(datasetId) {
    return fetch(API + '/dataset', {
      body: JSON.stringify({id: datasetId}),
      method: 'DELETE',
      headers: {Authorization: 'Bearer ' + getIdToken()},
    });
  }

  upsertDatasetPromise(data) {
    const isEdit = data.id != null;
    const formData = new FormData();
    for (let key in data) {
      let value = data[key];
      if (value != null) {
        if (isArray(value)) {
          value = JSON.stringify(value);
        }
        formData.append(key, value);
      }
    }
    const request = new XMLHttpRequest();
    request.open(isEdit ? 'PUT' : 'POST', API + '/dataset');
    request.setRequestHeader('Authorization', 'Bearer ' + getIdToken());

    // request.addEventListener('load', function (e) {
    //     // HTTP status message (200, 404 etc)
    //     console.log('load', request.status);
    //
    //     // request.response holds response from the server
    //     console.log('load', request.response);
    // });
    request.send(formData);
    return request;
  }

  getDatasetPromise(datasetId) {
    return fetch(API + '/dataset?id=' + datasetId, {
      method: 'GET',
      headers: {Authorization: 'Bearer ' + getIdToken()},
    }).then((response) => jsonResponse(response));
  }

  // category names
  getCategoryNamesPromise(datasetId) {
    return fetch(API + '/category_name?id=' + datasetId, {
      headers: {Authorization: 'Bearer ' + getIdToken()},
    }).then((response) => jsonResponse(response));
  }

  setCategoryNamePromise(data) {
    return fetch(API + '/category_name', {
      body: JSON.stringify(data),
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + getIdToken(),
      },
    });
  }

  // views
  getViewsPromise(datasetId) {
    return fetch(API + '/views?id=' + datasetId, {
      headers: {Authorization: 'Bearer ' + getIdToken()},
    }).then((response) => jsonResponse(response));
  }

  upsertViewPromise(data, isUpdate) {
    return fetch(API + '/view', {
      body: JSON.stringify(data),
      method: isUpdate ? 'PUT' : 'POST',
      headers: {Authorization: 'Bearer ' + getIdToken()},
    }).then((response) => jsonResponse(response));
  }

  deleteViewPromise(viewId, datasetId) {
    return fetch(API + '/view', {
      body: JSON.stringify({id: viewId, ds_id: datasetId}),
      method: 'DELETE',
      headers: {Authorization: 'Bearer ' + getIdToken()},
    });
  }

  getViewPromise(viewId) {
    return fetch(API + '/view?id=' + viewId, {
      headers: {Authorization: 'Bearer ' + getIdToken()},
    }).then((response) => jsonResponse(response));
  }

  // feature sets
  upsertFeatureSet(data, isUpdate) {
    return fetch(API + '/feature_set', {
      body: JSON.stringify(data),
      method: isUpdate ? 'PUT' : 'POST',
      headers: {Authorization: 'Bearer ' + getIdToken()},
    }).then((response) => jsonResponse(response));
  }

  deleteFeatureSet(setId, datasetId) {
    return fetch(API + '/feature_set', {
      body: JSON.stringify({id: setId, ds_id: datasetId}),
      method: 'DELETE',
      headers: {Authorization: 'Bearer ' + getIdToken()},
    });
  }

  exportDatasetFiltersPromise(datasetId) {
    return fetch(API + '/export_filters?id=' + datasetId, {
      headers: {Authorization: 'Bearer ' + getIdToken()},
    }).then((result) => {
      if (!result.ok) {
        return null;
      }
      return result.text();
    });
  }

  submitJob(data) {
    return fetch(API + '/job', {
      body: JSON.stringify(data),
      method: 'POST',
      headers: {Authorization: 'Bearer ' + getIdToken()},
    }).then((response) => jsonResponse(response));
  }
}
