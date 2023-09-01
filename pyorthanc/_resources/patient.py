import warnings
from datetime import datetime
from typing import Dict, List, Union

from .resource import Resource
from .study import Study
from .. import util
from ..jobs import Job


class Patient(Resource):
    """Represent a Patient that is in an Orthanc server

    This object has many getters that allow the user to retrieve metadata
    or the entire DICOM file of the Patient
    """

    def get_main_information(self) -> Dict:
        """Get Patient information

        Returns
        -------
        Dict
            Dictionary of patient main information.
        """
        if self.lock:
            if self._information is None:
                # Setup self._information for the first time when patient is lock
                self._information = self.client.get_patients_id(self.id_)

            return self._information

        return self.client.get_patients_id(self.id_)

    @property
    def patient_id(self) -> str:
        """Get patient ID"""
        return self._get_main_dicom_tag_value('PatientID')

    @property
    def name(self) -> str:
        """Get patient name"""
        return self._get_main_dicom_tag_value('PatientName')

    @property
    def birth_date(self) -> datetime:
        """Get patient birthdate"""
        date = self._get_main_dicom_tag_value('PatientBirthDate')

        return util.make_datetime_from_dicom_date(date)

    @property
    def sex(self) -> str:
        """Get patient sex"""
        return self._get_main_dicom_tag_value('PatientSex')

    @property
    def other_patient_ids(self) -> str:
        return self._get_main_dicom_tag_value('OtherPatientIDs').split('\\')

    @property
    def is_stable(self):
        return self.get_main_information()['IsStable']

    @property
    def last_update(self) -> datetime:
        last_updated_date_and_time = self.get_main_information()['LastUpdate'].split('T')
        date = last_updated_date_and_time[0]
        time = last_updated_date_and_time[1]

        return util.make_datetime_from_dicom_date(date, time)

    @property
    def labels(self) -> List[str]:
        return self.get_main_information()['Labels']

    def add_label(self, label: str) -> None:
        self.client.put_patients_id_labels_label(self.id_, label)

    def remove_label(self, label):
        self.client.delete_patients_id_labels_label(self.id_, label)

    def get_zip(self) -> bytes:
        """Get the bytes of the zip file

        Get the .zip file.

        Returns
        -------
        bytes
            Bytes of Zip file of the patient.

        Examples
        --------
        ```python
        from pyorthanc import Orthanc, Patient
        a_patient = Patient(
            'A_PATIENT_IDENTIFIER',
            Orthanc('http://localhost:8042')
        )
        bytes_content = a_patient.get_zip()
        with open('patient_zip_file_path.zip', 'wb') as file_handler:
            file_handler.write(bytes_content)
        ```

        """
        return self.client.get_patients_id_archive(self.id_)

    def get_patient_module(self, simplify: bool = False, short: bool = False) -> Dict:
        """Get patient module in a simplified version

        The method returns the DICOM patient module
        (PatientName, PatientID, PatientBirthDate, ...)

        Parameters
        ----------
        simplify
            Get the simplified version of the tags
        short
            Get the short version of the tags

        Returns
        -------
        Dict
            DICOM Patient module.
        """
        if simplify and not short:
            params = {'simplify': True}
        elif short and not simplify:
            params = {'short': True}
        elif simplify and short:
            raise ValueError('simplify and short can\'t be both True')
        else:
            params = {}

        return dict(self.client.get_patients_id_module(
            self.id_,
            params=params
        ))

    @property
    def protected(self) -> bool:
        """Get if patient is protected against recycling

        Protection against recycling: False means unprotected, True protected.

        Returns
        -------
        bool
            False means unprotected, True means protected.
        """
        return '1' == self.client.get_patients_id_protected(self.id_)

    @protected.setter
    def protected(self, value: bool):
        # As of version 1.11.1, the Orthanc OPEN API file has missing information
        self.client._put(
            f'{self.client.url}/patients/{self.id_}/protected',
            json=1 if value else 0  # 1 means it will be protected, 0 means unprotected
        )

    def is_protected(self) -> bool:
        """Get if patient is protected against recycling

        Protection against recycling: False means unprotected, True protected.

        Returns
        -------
        bool
            False means unprotected, True means protected.
        """
        DeprecationWarning(
            '`patient.is_protected()` is deprecated and will be removed in future release. '
            'Use `patient.protected` instead.'
        )
        return self.protected

    def set_to_protected(self):
        """Set patient to protected state

        Returns
        -------
        None
            Nothing.
        """
        # As of version 1.11.1, the Orthanc OPEN API file has missing information
        warnings.warn(
            '`patient.set_to_protected()` is deprecated and will be removed in future release. '
            'Use `patient.protected = True` instead.',
            DeprecationWarning
        )
        self.protected = True

    def set_to_unprotected(self):
        """Set patient to unprotected state

        Returns
        -------
        None
            Nothing.
        """
        # As of version 1.11.1, the Orthanc OPEN API file has missing information
        warnings.warn(
            '`patient.set_to_protected()` is deprecated and will be removed in future release. '
            'Use `patient.protected = True` instead.',
            DeprecationWarning
        )
        self.protected = False

    @property
    def studies(self) -> List[Study]:
        """Get patient's studies

        Returns
        -------
        List[Study]
            List of the patient's studies
        """
        if self.lock:
            if self._child_resources is None:
                studies_ids = self.get_main_information()['Studies']
                self._child_resources = [Study(i, self.client, self.lock) for i in studies_ids]

            return self._child_resources

        studies_ids = self.get_main_information()['Studies']

        return [Study(i, self.client, self.lock) for i in studies_ids]

    def anonymize(self, remove: List = None, replace: Dict = None, keep: List = None,
                  asynchronous: bool = False, force: bool = False, keep_private_tags: bool = False,
                  keep_source: bool = True, priority: int = 0, permissive: bool = False,
                  dicom_version: str = None) -> Union['Patient', Job]:
        """Anonymize patient

        If no error has been raise, then it creates a new anonymous patient.
        Documentation: https://book.orthanc-server.com/users/anonymization.html

        Parameters
        ----------
        remove
            List of tag to remove
        replace
            Dictionary of {tag: new_content}
        keep
            List of tag to keep unchanged
        asynchronous
            If True, run the job in asynchronous mode, which means that the method immediately
            return a job object. __Prefer this flavor wherever possible.__
        force
            Some tags can't be changed without forcing it (e.g. PatientID) for security reason
        keep_private_tags
            If True, keep the private tags from the DICOM instances.
        keep_source
            If False, instructs Orthanc to the remove original resources.
            By default, the original resources are kept in Orthanc.
        priority
            In asynchronous mode, the priority of the job. The lower the value, the higher the priority.
        permissive
            If True, ignore errors during the individual steps of the job.
        dicom_version
            Version of the DICOM standard to be used for anonymization.
            Check out configuration option DeidentifyLogsDicomVersion for possible values.

        Returns
        -------
        Union[Patient, Job]
            A New anonymous patient or Job if asynchronous=True.

        Examples
        --------
        Naive anonymization
        ```python
        new_patient = patient.anonymize()

        new_patient_with_specific_patient_id = patient.anonymize(
            keep=['PatientName'],
            replace={'PatientID': 'TheNewPatientID'},
            force=True
        )
        ```
        For large patient (recommended)
        ```python
        job = patient.anonymize(asynchronous=True)
        job.state
        job.block_until_completion()
        new_patient = Patient(job.content['ID'], orthanc)
        ```
        """
        remove = [] if remove is None else remove
        replace = {} if replace is None else replace
        keep = [] if keep is None else keep

        data = {
            'Remove': remove,
            'Replace': replace,
            'Keep': keep,
            'Force': force,
            'Asynchronous': asynchronous,
            'KeepPrivateTags': keep_private_tags,
            'KeepSource': keep_source,
            'Priority': priority,
            'Permissive': permissive,
        }
        if dicom_version is not None:
            data['DicomVersion'] = dicom_version

        anonymous_patient_or_job = self.client.post_patients_id_anonymize(self.id_, data)

        if asynchronous:
            return Job(anonymous_patient_or_job['ID'], self.client)

        return Patient(anonymous_patient_or_job['ID'], self.client)

    def remove_empty_studies(self) -> None:
        """Delete empty studies."""
        if self._child_resources is None:
            return

        for study in self._child_resources:
            study.remove_empty_series()

        self._child_resources = [study for study in self._child_resources if study._child_resources != []]
